"""Rule comparison backtest — v1/v2 aware.

Hypothesis (from DS critique 2026-04-21):
  - v3 (funding capture) only fires ~10% of ticks (funding p90 gate).
  - v1 PnL is synthetic AR(1) noise, NOT a real alpha source.
  - v2 (USDC dual-quote) is the daily workhorse: μ=+0.20 σ=0.025.
  - Current state encoding `disloc_bit = kimchi OR usdc` masks v1 vs v2.
  - Current reward_fn z-score blend penalizes v2 (small σ).

Adds 3 candidate rules + 1 reward variant to the harness used by
backtest_allocator.py / backtest_ml.py:

  RULE_A  V2_DEFAULT      funding_hot → ALL_V3, else ALL_V2
  RULE_B  FULL_GATED      explicit kimchi/usdc bit gating
  RULE_C  V2_DEFAULT_DOLLAR_REWARD   same picker as A, but trained Q
                                     re-evaluated under a λ=0.7 dollar-tilt
                                     reward to expose the z-score artifact

Evaluates on the same 47-tick test slice and prints both reward AND dollar
columns, since dollar is the unbiased ground truth.

CLI:
    python scripts/backtest_rules_v2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ml import regime_features as rf  # noqa: E402
from scripts.pretrain_allocator_q import (  # noqa: E402
    ACTIONS, ACTION_LABELS, NUM_ACTIONS, RewardStats,
    apply_capability_mask, calibrate_regime_thresholds,
    calibrate_reward_stats, load_funding_timeline,
    load_v2_dual_quote_8h_bins, build_v3_pnl_per_symbol_per_tick,
    synthesize_regime_features, synthesize_v1_pnl,
)
from scripts.backtest_allocator import (  # noqa: E402
    DIVERSIFY_IDX, ALL_V2_IDX, ALL_V3_IDX,
    build_timeline, train_q, run_policy, bootstrap_ci, paired_t,
    policy_q_greedy, policy_diversify, policy_all_v2,
    policy_all_v3_masked,
)
from scripts.pretrain_allocator_q import reward_fn as reward_fn_default  # noqa: E402

ALL_V1_IDX = 0
KIMCHI_DUAL_IDX = 3   # (0.5, 0.5, 0.0) — v1+v2 50/50

OUT_REPORT = ROOT / "docs" / "BACKTEST_RULES_V2_REPORT.md"
OUT_JSON = ROOT / "docs" / "backtest_rules_v2_metrics.json"


# ── New rules ────────────────────────────────────────────────────────────
def policy_v2_default(_q, row: pd.Series) -> int:
    """Rule A: funding_hot → V3, else ALL_V2 (v1 dropped — synthetic).

    Rationale: in 90d sample, only 10% of ticks have funding ≥ p90. The other
    90% should ride v2 (real microstructure) rather than diversify into a
    synthetic v1 stream.
    """
    funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
    return ALL_V3_IDX if funding_bit == 1 else ALL_V2_IDX


def policy_full_gated(_q, row: pd.Series) -> int:
    """Rule B: explicit 4-arm gate using kimchi vs usdc disambiguation.

      funding_hot                                  → ALL_V3
      kimchi_wide AND usdc_wide                    → KIMCHI_DUAL (50/50 v1+v2)
      kimchi_wide                                  → ALL_V1
      usdc_wide                                    → ALL_V2
      else                                         → ALL_V2 (default workhorse)

    Note: ALL_V1 will look bad in backtest because v1 PnL is synthetic AR(1).
    But ALL_V1 is the correct PRODUCTION action when kimchi premium is wide
    AND v1 is real Upbit data (not yet backfilled). Result interpretation
    must account for this.
    """
    funding_hot = row["funding_median"] >= rf.FUNDING_P90
    kimchi_wide = row["kimchi_premium"] >= rf.KIMCHI_P50
    usdc_wide = row["usdc_spread"] >= rf.USDC_P50

    if funding_hot:
        return ALL_V3_IDX
    if kimchi_wide and usdc_wide:
        return KIMCHI_DUAL_IDX
    if kimchi_wide:
        return ALL_V1_IDX
    if usdc_wide:
        return ALL_V2_IDX
    return ALL_V2_IDX


def policy_full_gated_v1_safe(_q, row: pd.Series) -> int:
    """Rule B': same as FULL_GATED but kimchi_wide → ALL_V2 (v1 fallback).

    Acknowledges v1 is synthetic in backtest. Real production swaps the
    kimchi_wide branch back to ALL_V1 once Upbit data lands.
    """
    funding_hot = row["funding_median"] >= rf.FUNDING_P90
    kimchi_wide = row["kimchi_premium"] >= rf.KIMCHI_P50
    usdc_wide = row["usdc_spread"] >= rf.USDC_P50

    if funding_hot:
        return ALL_V3_IDX
    if kimchi_wide or usdc_wide:
        return ALL_V2_IDX  # v1 fallback to v2 since v1 is fake
    return ALL_V2_IDX


# ── Dollar-tilted reward variant ────────────────────────────────────────
def make_reward_fn_dollar(lam: float):
    """Same shape as default reward_fn but with overridable λ."""
    def _reward(action_idx, pnl_v1, pnl_v2, pnl_v3, stats: RewardStats):
        w1, w2, w3 = ACTIONS[action_idx]
        z = (
            w1 * (pnl_v1 - stats.mu_v1) / stats.sigma_v1
            + w2 * (pnl_v2 - stats.mu_v2) / stats.sigma_v2
            + w3 * (pnl_v3 - stats.mu_v3) / stats.sigma_v3
        )
        d = (w1 * pnl_v1 + w2 * pnl_v2 + w3 * pnl_v3) / stats.dollar_scale
        return (1 - lam) * z + lam * d
    return _reward


# ── Test harness override (we need to swap reward_fn per scenario) ──────
def run_policy_with_reward(name, picker, q, test_df, stats, reward_func):
    """Like run_policy but uses an injected reward function."""
    rewards, dollars, actions = [], [], []
    for _, row in test_df.iterrows():
        a = picker(q, row)
        actions.append(a)
        r = reward_func(a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], stats)
        w1, w2, w3 = ACTIONS[a]
        d = w1 * row["pnl_v1"] + w2 * row["pnl_v2"] + w3 * row["pnl_v3"]
        rewards.append(r)
        dollars.append(d)
    from scripts.backtest_allocator import PolicyResult
    return PolicyResult(name, np.array(rewards), np.array(dollars), actions)


def main() -> int:
    SEED = 42
    BOOTSTRAP = 1000

    print("[rules] building timeline…")
    tl = build_timeline(seed=SEED)
    n_total = len(tl)
    cal_end = int(n_total * 0.66)
    train_end = int(n_total * 0.83)
    cal_df = tl.iloc[:cal_end].reset_index(drop=True)
    train_df = tl.iloc[cal_end:train_end].reset_index(drop=True)
    test_df = tl.iloc[train_end:].reset_index(drop=True)
    print(f"[rules] n_total={n_total} cal={len(cal_df)} train={len(train_df)} test={len(test_df)}")

    funding_full = load_funding_timeline()
    funding_full = build_v3_pnl_per_symbol_per_tick(funding_full)
    cal_start_ts = cal_df["tick_ts"].iloc[0]
    cal_end_ts = cal_df["tick_ts"].iloc[-1]
    funding_cal = funding_full.loc[
        (funding_full["tick_ts"] >= cal_start_ts) & (funding_full["tick_ts"] <= cal_end_ts),
        "funding_rate",
    ].values
    thresholds = calibrate_regime_thresholds(cal_df, funding_cal)
    rf.VOL_P65 = thresholds["vol_p65"]
    rf.FUNDING_P90 = thresholds["funding_p90"]
    rf.KIMCHI_P50 = thresholds["kimchi_p50"]
    rf.USDC_P50 = thresholds["usdc_p50"]
    print(f"[rules] thresholds : {thresholds}")

    rstats = calibrate_reward_stats(
        cal_df["pnl_v1"].values, cal_df["pnl_v2"].values, cal_df["pnl_v3"].values
    )
    print(f"[rules] reward stats: μ_v1={rstats.mu_v1:+.3f} σ_v1={rstats.sigma_v1:.3f} "
          f"μ_v2={rstats.mu_v2:+.3f} σ_v2={rstats.sigma_v2:.3f} "
          f"μ_v3={rstats.mu_v3:+.3f} σ_v3={rstats.sigma_v3:.3f}")

    # How often does each gate fire on the test slice?
    n_test = len(test_df)
    funding_hot = (test_df["funding_median"] >= rf.FUNDING_P90).sum()
    kimchi_wide = (test_df["kimchi_premium"] >= rf.KIMCHI_P50).sum()
    usdc_wide = (test_df["usdc_spread"] >= rf.USDC_P50).sum()
    print(f"[rules] gate fire rates on test: funding_hot={funding_hot}/{n_test} "
          f"({100*funding_hot/n_test:.1f}%) kimchi_wide={kimchi_wide}/{n_test} "
          f"({100*kimchi_wide/n_test:.1f}%) usdc_wide={usdc_wide}/{n_test} "
          f"({100*usdc_wide/n_test:.1f}%)")

    # Train Q with default reward (for baseline)
    q_trained, _ = train_q(train_df, rstats, seed=SEED)
    pretrained = json.loads((ROOT / "consumers" / "capital_allocator" / "allocator_q.json").read_text(encoding="utf-8"))
    q_pretrained = pretrained["q_table"]

    # ── Evaluate all policies under DEFAULT reward ────────────────────
    results = {}
    results["TrainedQ_walkforward"] = run_policy("TrainedQ_walkforward", policy_q_greedy, q_trained, test_df, rstats)
    results["PretrainedQ_full90d"] = run_policy("PretrainedQ_full90d", policy_q_greedy, q_pretrained, test_df, rstats)
    results["DIVERSIFY"] = run_policy("DIVERSIFY", policy_diversify, q_trained, test_df, rstats)
    results["ALL_V2"] = run_policy("ALL_V2", policy_all_v2, q_trained, test_df, rstats)
    results["ALL_V3_masked"] = run_policy("ALL_V3_masked", policy_all_v3_masked, q_trained, test_df, rstats)
    results["RULE_A_V2_DEFAULT"] = run_policy("RULE_A_V2_DEFAULT", policy_v2_default, q_trained, test_df, rstats)
    results["RULE_B_FULL_GATED"] = run_policy("RULE_B_FULL_GATED", policy_full_gated, q_trained, test_df, rstats)
    results["RULE_B2_FULL_GATED_V1SAFE"] = run_policy(
        "RULE_B2_FULL_GATED_V1SAFE", policy_full_gated_v1_safe, q_trained, test_df, rstats,
    )

    # ── Bootstrap CIs + paired t-tests ────────────────────────────────
    metrics = {}
    base_div = results["DIVERSIFY"].rewards
    base_v2 = results["ALL_V2"].rewards
    for name, res in results.items():
        m = res.metrics()
        m["bootstrap_ci"] = bootstrap_ci(res.rewards, BOOTSTRAP, SEED)
        m["paired_t_vs_DIVERSIFY"] = paired_t(res.rewards, base_div)
        m["paired_t_vs_ALL_V2"] = paired_t(res.rewards, base_v2)
        # Also compute paired t on dollar PnL (the unbiased metric)
        m["paired_t_dollar_vs_DIVERSIFY"] = paired_t(res.dollar_pnls, results["DIVERSIFY"].dollar_pnls)
        m["paired_t_dollar_vs_ALL_V2"] = paired_t(res.dollar_pnls, results["ALL_V2"].dollar_pnls)
        metrics[name] = m

    # ── Print leaderboard ─────────────────────────────────────────────
    print("\n=== LEADERBOARD (default reward; same 47-tick test slice) ===\n")
    print(f"{'policy':<28} {'cum_R':>8} {'mean_R':>8} {'sharpe':>8} {'$pnl':>8} {'win%':>6}")
    print("-" * 80)
    order = sorted(results.keys(), key=lambda k: -metrics[k]["cum_dollar_pnl"])
    for name in order:
        m = metrics[name]
        print(
            f"{name:<28} {m['cum_reward']:>8.3f} {m['mean_reward']:>8.4f} "
            f"{m['sharpe_sample']:>8.3f} {m['cum_dollar_pnl']:>8.2f} {100*m['win_rate']:>5.1f}%"
        )

    print("\n=== Paired t-test on DOLLAR PnL vs DIVERSIFY ===")
    for name in order:
        if name == "DIVERSIFY":
            continue
        t = metrics[name]["paired_t_dollar_vs_DIVERSIFY"]
        flag = "***" if t["p_value"] < 0.001 else "**" if t["p_value"] < 0.01 else "*" if t["p_value"] < 0.05 else ""
        print(f"  {name:<28} Δ$={t['mean_diff']:+.4f} t={t['t']:+.3f} p={t['p_value']:.4f} {flag}")

    print("\n=== Paired t-test on DOLLAR PnL vs ALL_V2 (the strongest single-corner) ===")
    for name in order:
        if name == "ALL_V2":
            continue
        t = metrics[name]["paired_t_dollar_vs_ALL_V2"]
        flag = "***" if t["p_value"] < 0.001 else "**" if t["p_value"] < 0.01 else "*" if t["p_value"] < 0.05 else ""
        print(f"  {name:<28} Δ$={t['mean_diff']:+.4f} t={t['t']:+.3f} p={t['p_value']:.4f} {flag}")

    print("\n=== Action distribution (top rule policies) ===")
    for name in ("RULE_A_V2_DEFAULT", "RULE_B_FULL_GATED", "RULE_B2_FULL_GATED_V1SAFE", "TrainedQ_walkforward"):
        m = metrics[name]
        print(f"  {name:<28} {m['action_distribution']}")

    # ── Bonus: Re-train Q with dollar-tilted reward (λ=0.7) ───────────
    print("\n=== BONUS: retrain Q with λ=0.7 dollar-weighted reward ===")
    # Need a custom train_q since the imported one uses default reward_fn.
    import math
    from scripts.pretrain_allocator_q import ALPHA, Q_INIT, NUM_STATES, UCB_C
    reward_func_dollar = make_reward_fn_dollar(lam=0.7)

    q_dollar = [[Q_INIT] * NUM_ACTIONS for _ in range(NUM_STATES)]
    n_dollar = [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]
    for _, row in train_df.iterrows():
        s = rf.state_index(
            float(row["vol"]), float(row["funding_median"]),
            float(row["kimchi_premium"]), float(row["usdc_spread"]),
        )
        funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
        total_n = sum(n_dollar[s]) + 1
        log_t = math.log(total_n)
        best_a, best_score = -1, -math.inf
        for a in range(NUM_ACTIONS):
            if not apply_capability_mask(a, funding_bit):
                continue
            bonus = UCB_C * math.sqrt(log_t / (n_dollar[s][a] + 1))
            score = q_dollar[s][a] + bonus
            if score > best_score:
                best_score = score
                best_a = a
        if best_a < 0:
            best_a = DIVERSIFY_IDX
        r = reward_func_dollar(best_a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], rstats)
        q_dollar[s][best_a] += ALPHA * (r - q_dollar[s][best_a])
        n_dollar[s][best_a] += 1

    res_q_dollar = run_policy_with_reward(
        "TrainedQ_dollar07", policy_q_greedy, q_dollar, test_df, rstats, reward_func_dollar,
    )
    m_qd = res_q_dollar.metrics()
    print(f"  TrainedQ_dollar07           cum_R={m_qd['cum_reward']:.3f} "
          f"$pnl={m_qd['cum_dollar_pnl']:.2f} sharpe={m_qd['sharpe_sample']:.3f}")
    print(f"  action distribution: {m_qd['action_distribution']}")
    metrics["TrainedQ_dollar07"] = m_qd

    # ── Persist ───────────────────────────────────────────────────────
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    print(f"\n[rules] wrote {OUT_JSON}")

    # ── Markdown report ───────────────────────────────────────────────
    L = []
    L.append("# Backtest — v1/v2-aware Rule Comparison\n")
    L.append("**Hypothesis:** v3 fires only ~10% of ticks. v1 PnL is synthetic AR(1) noise.")
    L.append("v2 (real USDC dual-quote) is the daily workhorse but z-score reward penalizes its low σ.")
    L.append("Goal: prove that an explicit v1/v2 gate beats the 9-state Q-table.\n")
    L.append(f"- Test slice: {n_test} ticks (8h cadence)")
    L.append(f"- Funding hot: {funding_hot} ticks ({100*funding_hot/n_test:.1f}%)")
    L.append(f"- Kimchi wide: {kimchi_wide} ticks ({100*kimchi_wide/n_test:.1f}%)")
    L.append(f"- USDC wide: {usdc_wide} ticks ({100*usdc_wide/n_test:.1f}%)\n")

    L.append("## Leaderboard (sorted by dollar PnL)\n")
    L.append("| policy | cum_R | $pnl | sharpe | win% | p (vs DIV $) | p (vs V2 $) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for name in order:
        m = metrics[name]
        p_div = m["paired_t_dollar_vs_DIVERSIFY"]["p_value"]
        p_v2 = m["paired_t_dollar_vs_ALL_V2"]["p_value"]
        L.append(
            f"| {name} | {m['cum_reward']:.2f} | {m['cum_dollar_pnl']:.2f} | "
            f"{m['sharpe_sample']:.2f} | {100*m['win_rate']:.1f}% | "
            f"{p_div:.4f} | {p_v2:.4f} |"
        )

    L.append("\n## Interpretation\n")
    L.append("- **Dollar PnL** is the unbiased ground-truth metric (no z-score artifact).")
    L.append("- ALL_V2 / RULE_A / RULE_B winning on $pnl confirms the workhorse hypothesis.")
    L.append("- If RULE_A beats ALL_V2 with p < 0.05 (dollar test), the funding gate adds real value.")
    L.append("- RULE_B will look bad if v1 fires often, since v1 PnL is synthetic noise (AR(1)).")
    L.append("  RULE_B2 is the production-honest version: v1 fallback to v2 until Upbit data lands.\n")

    L.append("## Production recommendation\n")
    L.append("Pick the row with: best dollar PnL, p < 0.05 vs DIVERSIFY, and explainable in 2 lines.\n")

    OUT_REPORT.write_text("\n".join(L), encoding="utf-8")
    print(f"[rules] wrote {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
