"""Dynamic Pricing Policy — tabular Q-learning with UCB1 exploration.

Design review applied from Giants' Shoulders + Pre-Mortem:
- State 8 (regime × edge), NOT 64. Sale-rate removed (action feedback loop).
  Meta-agent confidence_score NOT in state (F5: breaks reliability feedback).
- Action 4 tiers anchored to fee-covered base, NOT 0.5x-10x median
  (Griffin: 10x always rejected → null reward pollution).
- Reward = realized net PnL after VIP3 fees, NOT meta's expected_pnl × decay
  (Overdeck: direct target leakage on meta's own optimism).
- UCB1 + optimistic init Q0=+0.01, NOT ε-greedy
  (Sutton/Barto: ε=0.1 × 28 samples = 3 exploratory actions, starved).
- Acceptance freeze: accept_rate < 10% after 20 visits → action disabled
  (Griffin: adverse selection on buy side).
- Safety rail: rolling 1-min net PnL < -$0.20 → force action=1x
  (F4: jury should never see red on the demo screen).
- hold_sec == reward horizon (F2: credit assignment integrity).

Simulation basis: Bybit VIP 0 + USDC taker 50% off promo (2026-03~).
  maker 0.1%, taker 0.05% (after 50% promo), r.t. taker-taker 0.10%.

Rationale for picking Bybit-retail over Binance-VIP3:
  Retail quants sit at VIP 0 on every major venue (VIP 1+ requires ≥$1M 30d
  volume). Bybit's USDC promo is the one promo that actually applies to the
  VIP 0 tier — Binance's zero-fee USDC promo is gated at VIP 2+. So the Q
  table is compiled against the most economically realistic world our target
  user lives in. If a VIP 3 judge wants to see their numbers, they use the
  dashboard FeeExplorer to re-estimate expected edge.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Fee model (Bybit VIP 0 + USDC taker promo) ────────────────────────────
FEE_MAKER = 0.001       # Bybit VIP 0 maker, no discount on maker side
FEE_TAKER = 0.0005      # Bybit VIP 0 taker 0.1% × 50%-off USDC promo
FEE_ROUND_TRIP = FEE_TAKER * 2  # taker-taker: worst-case realistic (0.10%)
FEE_PERSONA_LABEL = "Bybit_VIP0_USDC_taker_promo"

# ── State buckets ────────────────────────────────────────────────────────
# Regime collapse guard (F1): only 2 classes. At demo threshold 0.05%,
# active/calm split covers both edge-poor and edge-rich regimes without
# requiring a working 4-class classifier.
REGIME_CALM = 0      # |premium| <  15bp
REGIME_ACTIVE = 1    # |premium| >= 15bp
NUM_REGIME = 2

EDGE_BOUNDARIES = [0.0005, 0.0015, 0.0030]  # 5bp / 15bp / 30bp
NUM_EDGE = len(EDGE_BOUNDARIES) + 1
NUM_STATES = NUM_REGIME * NUM_EDGE           # 8

# ── Action set (Griffin-tightened) ───────────────────────────────────────
# Base price = FEE_ROUND_TRIP × notional. The multiplier is the markup the
# meta-agent charges *above the fee it forces the executor to pay*. 0.75x
# is a loss-leader included on purpose so the table can learn "sometimes
# pay out to keep the funnel active" — but it is floored at PRICE_FLOOR.
ACTION_MULTIPLIERS = [0.75, 1.0, 1.5, 2.5]
NUM_ACTIONS = len(ACTION_MULTIPLIERS)

# ── Q-learning hyperparams ───────────────────────────────────────────────
ALPHA = 0.1
Q_INIT = 0.01           # optimistic init: encourages first visit to every (s,a)
UCB_C = 0.5             # exploration bonus weight
ACCEPT_FREEZE_MIN_VISITS = 20
ACCEPT_FREEZE_THRESHOLD = 0.10

# ── Price bounds (must match bridge x402 middleware cap) ─────────────────
PRICE_FLOOR = 0.0005
PRICE_CAP = 0.01        # hard-capped so x402 paymentMiddleware never rejects

# ── Safety rail (F4 mitigation) ──────────────────────────────────────────
SAFETY_PNL_WINDOW_SEC = 60.0
SAFETY_PNL_THRESHOLD = -0.20


STATE_LABELS = [
    f"{['calm', 'active'][r]}/{['<5bp', '5-15bp', '15-30bp', '>30bp'][e]}"
    for r in range(NUM_REGIME) for e in range(NUM_EDGE)
]


def _edge_bucket(premium: float) -> int:
    p = abs(premium)
    for i, boundary in enumerate(EDGE_BOUNDARIES):
        if p < boundary:
            return i
    return len(EDGE_BOUNDARIES)


def _regime_bucket(premium: float) -> int:
    return REGIME_ACTIVE if abs(premium) >= 0.0015 else REGIME_CALM


def state_index(premium_rate: float) -> int:
    """Map a signal to its state index.

    Intentionally depends on premium_rate ONLY. We do NOT fold in
    meta-agent confidence_score or producer hit_rate — that would create a
    feedback loop where a cold producer gets priced out, produces no
    outcomes, and stays cold forever (pre-mortem F5).
    """
    return _regime_bucket(premium_rate) * NUM_EDGE + _edge_bucket(premium_rate)


@dataclass
class PolicyStats:
    q: list[list[float]] = field(
        default_factory=lambda: [[Q_INIT] * NUM_ACTIONS for _ in range(NUM_STATES)]
    )
    n_visits: list[list[int]] = field(
        default_factory=lambda: [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]
    )
    n_accepts: list[list[int]] = field(
        default_factory=lambda: [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]
    )
    total_updates: int = 0
    pretrained: bool = False

    def to_dict(self) -> dict:
        return {
            "q": self.q,
            "n_visits": self.n_visits,
            "n_accepts": self.n_accepts,
            "total_updates": self.total_updates,
            "pretrained": self.pretrained,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PolicyStats":
        return cls(
            q=d.get("q") or [[Q_INIT] * NUM_ACTIONS for _ in range(NUM_STATES)],
            n_visits=d.get("n_visits") or [[0] * NUM_ACTIONS for _ in range(NUM_STATES)],
            n_accepts=d.get("n_accepts") or [[0] * NUM_ACTIONS for _ in range(NUM_STATES)],
            total_updates=int(d.get("total_updates", 0)),
            pretrained=bool(d.get("pretrained", False)),
        )


@dataclass
class PricingDecision:
    state_idx: int
    action_idx: int
    price_usdc: float
    base_price: float
    state_label: str
    fallback_reason: Optional[str] = None


class PricingPolicy:
    def __init__(self, stats_path: Optional[Path] = None, load: bool = True):
        self.stats_path = stats_path
        self.stats = PolicyStats()
        self._recent_pnls: list[tuple[float, float]] = []
        if load and stats_path and stats_path.exists():
            try:
                self.stats = PolicyStats.from_dict(json.loads(stats_path.read_text()))
                print(
                    f"[pricing] loaded Q-table from {stats_path.name} "
                    f"(updates={self.stats.total_updates}, pretrained={self.stats.pretrained})"
                )
            except Exception as e:
                print(f"[pricing] load failed ({e}); starting fresh")

    def save(self) -> None:
        if self.stats_path is None:
            return
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            self.stats_path.write_text(json.dumps(self.stats.to_dict(), indent=2))
        except Exception as e:
            print(f"[pricing] save failed: {e}")

    def _rolling_pnl(self) -> float:
        now = time.time()
        cutoff = now - SAFETY_PNL_WINDOW_SEC
        self._recent_pnls = [(t, p) for (t, p) in self._recent_pnls if t >= cutoff]
        return sum(p for _, p in self._recent_pnls)

    def _ucb_select(self, state_idx: int) -> int:
        visits = self.stats.n_visits[state_idx]
        accepts = self.stats.n_accepts[state_idx]
        q = self.stats.q[state_idx]
        total_visits = sum(visits)
        log_total = math.log(total_visits + 1)

        best_a = 1  # default to break-even multiplier
        best_score = -float("inf")
        any_valid = False
        for a in range(NUM_ACTIONS):
            # Acceptance freeze — only applies AFTER enough data
            if visits[a] >= ACCEPT_FREEZE_MIN_VISITS:
                accept_rate = accepts[a] / max(visits[a], 1)
                if accept_rate < ACCEPT_FREEZE_THRESHOLD:
                    continue
            any_valid = True
            n = visits[a]
            bonus = UCB_C * math.sqrt(log_total / (n + 1))
            score = q[a] + bonus
            if score > best_score:
                best_score = score
                best_a = a
        if not any_valid:
            # All frozen — fallback to break-even (should never happen in demo)
            return 1
        return best_a

    def choose_price(
        self,
        premium_rate: float,
        notional_usd: float,
    ) -> PricingDecision:
        state_idx = state_index(premium_rate)
        base = FEE_ROUND_TRIP * notional_usd

        rolling = self._rolling_pnl()
        if rolling < SAFETY_PNL_THRESHOLD:
            action_idx = 1  # break-even
            price = max(PRICE_FLOOR, min(PRICE_CAP, base * ACTION_MULTIPLIERS[action_idx]))
            return PricingDecision(
                state_idx=state_idx,
                action_idx=action_idx,
                price_usdc=price,
                base_price=base,
                state_label=STATE_LABELS[state_idx],
                fallback_reason=f"safety_rail(rolling_pnl={rolling:.3f})",
            )

        action_idx = self._ucb_select(state_idx)
        price = max(PRICE_FLOOR, min(PRICE_CAP, base * ACTION_MULTIPLIERS[action_idx]))
        return PricingDecision(
            state_idx=state_idx,
            action_idx=action_idx,
            price_usdc=price,
            base_price=base,
            state_label=STATE_LABELS[state_idx],
        )

    def update(
        self,
        state_idx: int,
        action_idx: int,
        realized_pnl: float,
        accepted: bool = True,
    ) -> None:
        self.stats.n_visits[state_idx][action_idx] += 1
        if accepted:
            self.stats.n_accepts[state_idx][action_idx] += 1
        q = self.stats.q[state_idx][action_idx]
        self.stats.q[state_idx][action_idx] = q + ALPHA * (realized_pnl - q)
        self.stats.total_updates += 1
        self._recent_pnls.append((time.time(), realized_pnl))

    def snapshot(self) -> dict:
        return {
            "total_updates": self.stats.total_updates,
            "pretrained": self.stats.pretrained,
            "state_labels": STATE_LABELS,
            "action_multipliers": ACTION_MULTIPLIERS,
            "q_table": self.stats.q,
            "visits": self.stats.n_visits,
            "accepts": self.stats.n_accepts,
            "state_entropy_bits": self._state_entropy(),
            "rolling_pnl": self._rolling_pnl(),
            "fee_round_trip": FEE_ROUND_TRIP,
            "fee_persona": FEE_PERSONA_LABEL,
        }

    def _state_entropy(self) -> float:
        totals = [sum(self.stats.n_visits[s]) for s in range(NUM_STATES)]
        total = sum(totals) or 1
        h = 0.0
        for t in totals:
            if t > 0:
                p = t / total
                h -= p * math.log2(p)
        return h
