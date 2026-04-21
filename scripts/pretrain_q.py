"""Offline Q-table pretraining -- Pre-Mortem F3 cold-start mitigation.

Problem the live executor has:
  In a 120s demo the exploration budget per cell is ~2-3 samples. UCB1 on 8
  states × 4 actions = 32 cells cannot converge in that time. The judge sees
  random-walk pricing, not "the agent learned to charge more in active
  regime". F3 calls this the single most-likely "looks unintelligent" failure.

Fix:
  Pretrain the Q-table offline against a synthetic MDP whose dynamics match
  the live simulator's `_simulate_realized_edge` (retention uniform[0.35,1.05]
  × entry_premium, 35% adverse-flip rate, small Gaussian noise). Pretraining
  gives every (state, action) cell thousands of samples so UCB1 starts warm
  and converges visibly on the demo screen.

Fairness guarantees:
  - Uses the SAME fee model (FEE_ROUND_TRIP) the live policy is compiled
    against. No leakage from a different persona.
  - Marks stats.pretrained = True so live code can gate behavior if needed.
  - Re-uses PricingPolicy.update() -- no duplicate math drift.

Usage:
    python -m scripts.pretrain_q --episodes 5000 \\
        --out consumers/executor_agent/q_table.json
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

# Make the "consumers" package importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from consumers.executor_agent.pricing_policy import (  # noqa: E402
    ACTION_MULTIPLIERS,
    EDGE_BOUNDARIES,
    FEE_ROUND_TRIP,
    NUM_STATES,
    PricingPolicy,
    state_index,
)


def sample_premium() -> float:
    """Draw a premium rate from a plausible v1.3 live distribution.

    Distribution, calibrated to day-4 backtest histograms:
      70% calm regime -- |premium| uniform in [0, 15bp]
      30% active regime -- |premium| uniform in [15bp, 50bp]
    Sign is balanced (BUY/SELL equally likely).
    """
    active = random.random() < 0.30
    if active:
        mag = random.uniform(0.0015, 0.0050)
    else:
        mag = random.uniform(0.0, 0.0015)
    sign = 1.0 if random.random() < 0.5 else -1.0
    return sign * mag


def sample_realized_edge(entry_premium: float) -> float:
    """Must match consumers/executor_agent/main.py::_simulate_realized_edge.

    Kept as a copy (not an import) so the pretraining trajectory is obviously
    aligned with the live simulator rather than at risk of drifting under a
    future refactor. If that function changes, this one MUST change in step.
    """
    retention = random.uniform(0.35, 1.05)
    sign = 1.0 if random.random() > 0.35 else -1.0
    mag = abs(entry_premium) * retention
    noise = random.gauss(0.0, 0.0001)
    return sign * mag + noise


def _simulate_step(policy: PricingPolicy, premium: float, action_idx: int, notional: float) -> float:
    """Apply a forced action (not chosen by UCB) and update the Q table.

    Used during warm-up so every (state, action) cell gets a fair read before
    UCB starts exploiting. Returns the realized net PnL so callers can log.
    """
    from consumers.executor_agent.pricing_policy import (  # local import avoids cycles
        ACTION_MULTIPLIERS as MULTIPLIERS,
        PRICE_FLOOR, PRICE_CAP,
    )
    state_idx = state_index(premium)
    base = FEE_ROUND_TRIP * notional
    price = max(PRICE_FLOOR, min(PRICE_CAP, base * MULTIPLIERS[action_idx]))
    realized = sample_realized_edge(premium)
    gross = realized * notional
    net = gross - FEE_ROUND_TRIP * notional - price
    policy.update(state_idx=state_idx, action_idx=action_idx, realized_pnl=net, accepted=True)
    return net


def run_pretrain(
    episodes: int,
    notional: float,
    seed: int | None,
    warmup_per_cell: int = 50,
) -> PricingPolicy:
    if seed is not None:
        random.seed(seed)

    # In-memory only during pretraining -- caller decides where to persist.
    policy = PricingPolicy(stats_path=None, load=False)

    # Phase 1: warm-up. Force every (state, action) cell to receive at least
    # `warmup_per_cell` samples. UCB1 alone under-explores low-Q actions when
    # Q_INIT is small relative to the fee cost — see Sutton/Barto §2.7 on
    # "optimistic initial values" limits. Fixing it here keeps the live
    # policy's bonus/exploitation balance untouched.
    from consumers.executor_agent.pricing_policy import NUM_ACTIONS as NA
    # We still need premia drawn from the target distribution so the
    # realized-edge variance per cell matches inference-time draws.
    targets = [(s, a) for s in range(NUM_STATES) for a in range(NA)]
    for s_target, a_target in targets:
        filled = 0
        attempts = 0
        while filled < warmup_per_cell and attempts < warmup_per_cell * 50:
            attempts += 1
            prem = sample_premium()
            if state_index(prem) != s_target:
                continue
            _simulate_step(policy, prem, a_target, notional)
            filled += 1

    # Phase 2: UCB exploration against the sampled premium distribution.
    for _ in range(episodes):
        premium = sample_premium()
        decision = policy.choose_price(premium, notional)
        realized = sample_realized_edge(premium)
        gross = realized * notional
        fee_cost = FEE_ROUND_TRIP * notional
        net = gross - fee_cost - decision.price_usdc
        policy.update(
            state_idx=decision.state_idx,
            action_idx=decision.action_idx,
            realized_pnl=net,
            accepted=True,
        )

    policy.stats.pretrained = True
    return policy


def report(policy: PricingPolicy) -> None:
    snap = policy.snapshot()
    print(f"\npretrain complete -- updates={policy.stats.total_updates}")
    print(f"entropy over states: {snap['state_entropy_bits']:.3f} bits")
    print(f"\nState × Action Q-values (dollar PnL at ~$100 notional):\n")
    header = "state".ljust(20) + " ".join(f"× {m:>4}".rjust(10) for m in ACTION_MULTIPLIERS)
    print(header)
    print("-" * len(header))
    for s in range(NUM_STATES):
        label = snap["state_labels"][s].ljust(20)
        row = " ".join(f"{policy.stats.q[s][a]:>10.4f}" for a in range(len(ACTION_MULTIPLIERS)))
        print(label + row)

    print("\nvisit counts per cell:")
    for s in range(NUM_STATES):
        label = snap["state_labels"][s].ljust(20)
        row = " ".join(f"{policy.stats.n_visits[s][a]:>10d}" for a in range(len(ACTION_MULTIPLIERS)))
        print(label + row)

    print(f"\nEDGE_BOUNDARIES = {EDGE_BOUNDARIES}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=5000)
    ap.add_argument("--warmup-per-cell", type=int, default=50,
                    help="minimum samples per (state, action) cell in the warm-up pass")
    ap.add_argument("--notional", type=float, default=100.0,
                    help="fixed notional used during pretraining; per-signal notional "
                         "at inference time scales the reward linearly but the policy's "
                         "comparative Q-values stay meaningful")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="consumers/executor_agent/q_table.json")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    policy = run_pretrain(
        args.episodes, args.notional, args.seed,
        warmup_per_cell=args.warmup_per_cell,
    )
    report(policy)

    if args.no_write:
        print("\n[pretrain] --no-write set -- skipping persistence")
        return
    policy.stats_path = Path(args.out)
    policy.save()
    print(f"\n[pretrain] wrote Q-table → {policy.stats_path}")


if __name__ == "__main__":
    main()
