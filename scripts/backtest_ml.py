"""Contextual-bandit re-cast: Q-table vs Ridge vs LightGBM.

DS critique: the allocator setup is NOT a real MDP — our action does not affect
next tick's vol/funding/kimchi/usdc (the market is much bigger than us), and
the cadence is 8h so there is zero time pressure. So this is a contextual
bandit, which collapses to supervised learning: predict per-strategy expected
pnl from current features, then argmax expected reward over 7 actions.

This script keeps the EXACT split used by backtest_allocator.py and adds two
supervised baselines:

    Ridge       — 3 separate ridge regressions, one per pnl_v{1,2,3}
    LightGBM    — 3 separate LightGBM regressors (small: depth 3, leaves 7)

Both use the same 4 continuous features the Q-table bins discretely:
    vol, funding_median, kimchi_premium, usdc_spread

At test time, we ask each model for predicted (pnl_v1, pnl_v2, pnl_v3) and
plug those into the same reward_fn used by the Q-table to score 7 actions,
then argmax with capability mask. Evaluation uses REAL test pnls — identical
metric pipeline to backtest_allocator.py for apples-to-apples comparison.

Data budget parity: every model fits on the same train slice (~46 ticks)
that the Q-table uses; cal slice is used by all three to compute reward stats
(μ_v1/σ_v1/...) that the reward function depends on. No model peeks at test.

Caveat: with 46 train rows, LightGBM is on the edge — small model +
regularization required, no early stopping (no held-out subset large enough).
We report this honestly in the markdown.

Usage:
    python scripts/backtest_ml.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
from scipy import stats as sstats
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import regime_features as rf  # noqa: E402
from scripts.pretrain_allocator_q import (  # noqa: E402
    ACTIONS, ACTION_LABELS, NUM_ACTIONS, RewardStats,
    apply_capability_mask, calibrate_regime_thresholds, calibrate_reward_stats,
    load_funding_timeline, build_v3_pnl_per_symbol_per_tick, reward_fn,
)
from scripts.backtest_allocator import (  # noqa: E402
    DIVERSIFY_IDX, ALL_V2_IDX, ALL_V3_IDX,
    PolicyResult, build_timeline, train_q,
    policy_q_greedy, policy_diversify, policy_all_v2, policy_all_v3_masked,
    policy_random, policy_oracle, run_policy, bootstrap_ci, paired_t,
)

OUT_REPORT = ROOT / "docs" / "BACKTEST_ML_REPORT.md"
OUT_JSON = ROOT / "docs" / "backtest_ml_metrics.json"

FEATURES = ["vol", "funding_median", "kimchi_premium", "usdc_spread"]


# ─────────────────────────────────────────────────────────────────────────
# Supervised models (3 per strategy)
# ─────────────────────────────────────────────────────────────────────────
class StrategyPnLModel:
    """3 regressors (one per pnl target). predict(features) → (pnl_v1, v2, v3)."""

    def __init__(self, kind: str, **kwargs):
        self.kind = kind
        self.kwargs = kwargs
        self.scaler = StandardScaler()
        self.models: dict[str, object] = {}

    def fit(self, X: np.ndarray, y: dict[str, np.ndarray]) -> None:
        Xs = self.scaler.fit_transform(X)
        for tgt in ("pnl_v1", "pnl_v2", "pnl_v3"):
            if self.kind == "ridge":
                m = Ridge(alpha=self.kwargs.get("alpha", 1.0), random_state=42)
                m.fit(Xs, y[tgt])
            elif self.kind == "lgbm":
                m = lgb.LGBMRegressor(
                    n_estimators=self.kwargs.get("n_estimators", 50),
                    num_leaves=self.kwargs.get("num_leaves", 7),
                    max_depth=self.kwargs.get("max_depth", 3),
                    min_data_in_leaf=self.kwargs.get("min_data_in_leaf", 5),
                    learning_rate=self.kwargs.get("learning_rate", 0.05),
                    reg_alpha=0.1, reg_lambda=0.1,
                    random_state=42,
                    verbose=-1,
                )
                m.fit(Xs, y[tgt])
            else:
                raise ValueError(f"unknown kind={self.kind}")
            self.models[tgt] = m

    def predict(self, X: np.ndarray) -> dict[str, np.ndarray]:
        Xs = self.scaler.transform(X)
        return {tgt: self.models[tgt].predict(Xs) for tgt in ("pnl_v1", "pnl_v2", "pnl_v3")}

    def feature_importance(self) -> dict[str, dict[str, float]]:
        out = {}
        for tgt, m in self.models.items():
            if self.kind == "ridge":
                # Coefficients on standardized features
                coefs = dict(zip(FEATURES, [float(c) for c in m.coef_]))
            elif self.kind == "lgbm":
                imp = m.feature_importances_
                coefs = dict(zip(FEATURES, [float(c) for c in imp]))
            else:
                coefs = {}
            out[tgt] = coefs
        return out


def policy_supervised(model: StrategyPnLModel, stats: RewardStats):
    """Returns picker(q, row) — uses model to pick best action."""
    def _pick(_q, row):
        x = np.array([[row[f] for f in FEATURES]])
        pred = model.predict(x)
        p1 = float(pred["pnl_v1"][0])
        p2 = float(pred["pnl_v2"][0])
        p3 = float(pred["pnl_v3"][0])
        funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
        best_a, best_r = -1, -math.inf
        for a in range(NUM_ACTIONS):
            if not apply_capability_mask(a, funding_bit):
                continue
            r = reward_fn(a, p1, p2, p3, stats)
            if r > best_r:
                best_r = r
                best_a = a
        return best_a if best_a >= 0 else DIVERSIFY_IDX
    return _pick


# ─────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--cal-end-pct", type=float, default=0.66)
    ap.add_argument("--train-end-pct", type=float, default=0.83)
    args = ap.parse_args()

    print("[ml] building timeline…")
    tl = build_timeline(seed=args.seed)
    n_total = len(tl)
    cal_end = int(n_total * args.cal_end_pct)
    train_end = int(n_total * args.train_end_pct)
    cal_df = tl.iloc[:cal_end].reset_index(drop=True)
    train_df = tl.iloc[cal_end:train_end].reset_index(drop=True)
    test_df = tl.iloc[train_end:].reset_index(drop=True)
    print(f"[ml] n_total={n_total} cal={len(cal_df)} train={len(train_df)} test={len(test_df)}")

    # Calibrate thresholds + reward stats on cal slice (same as Q-table backtest)
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
    rstats = calibrate_reward_stats(
        cal_df["pnl_v1"].values, cal_df["pnl_v2"].values, cal_df["pnl_v3"].values
    )
    print(f"[ml] thresholds   : {thresholds}")
    print(f"[ml] reward stats : μ_v1={rstats.mu_v1:+.3f} σ_v1={rstats.sigma_v1:.3f} "
          f"μ_v2={rstats.mu_v2:+.3f} σ_v2={rstats.sigma_v2:.3f} "
          f"μ_v3={rstats.mu_v3:+.3f} σ_v3={rstats.sigma_v3:.3f}")

    # ── Supervised model fits on train slice ──
    X_train = train_df[FEATURES].values
    y_train = {tgt: train_df[tgt].values for tgt in ("pnl_v1", "pnl_v2", "pnl_v3")}

    print(f"[ml] fitting Ridge on {len(train_df)} ticks…")
    ridge_model = StrategyPnLModel("ridge", alpha=1.0)
    ridge_model.fit(X_train, y_train)

    print(f"[ml] fitting LightGBM on {len(train_df)} ticks (depth=3 leaves=7 n=50)…")
    lgbm_model = StrategyPnLModel("lgbm", n_estimators=50, num_leaves=7, max_depth=3,
                                  min_data_in_leaf=5, learning_rate=0.05)
    lgbm_model.fit(X_train, y_train)

    # ── Q-table walk-forward (re-train on same slice for parity) ──
    print(f"[ml] training Q-table on same train slice (UCB1)…")
    q_trained, _ = train_q(train_df, rstats, seed=args.seed)

    # ── Pretrained Q (for leakage reference) ──
    pretrained_path = ROOT / "consumers" / "capital_allocator" / "allocator_q.json"
    pretrained = json.loads(pretrained_path.read_text(encoding="utf-8"))
    q_pretrained = pretrained["q_table"]

    # ── Run all policies ──
    print(f"[ml] evaluating on {len(test_df)} test ticks…")
    rng_random = np.random.default_rng(args.seed + 200)
    results: dict[str, PolicyResult] = {}
    results["Ridge"] = run_policy(
        "Ridge", policy_supervised(ridge_model, rstats), q_trained, test_df, rstats,
    )
    results["LightGBM"] = run_policy(
        "LightGBM", policy_supervised(lgbm_model, rstats), q_trained, test_df, rstats,
    )
    results["TrainedQ_walkforward"] = run_policy(
        "TrainedQ_walkforward", policy_q_greedy, q_trained, test_df, rstats,
    )
    results["PretrainedQ_full90d"] = run_policy(
        "PretrainedQ_full90d", policy_q_greedy, q_pretrained, test_df, rstats,
    )
    results["DIVERSIFY"] = run_policy(
        "DIVERSIFY", policy_diversify, q_trained, test_df, rstats,
    )
    results["ALL_V2"] = run_policy(
        "ALL_V2", policy_all_v2, q_trained, test_df, rstats,
    )
    results["ALL_V3_masked"] = run_policy(
        "ALL_V3_masked", policy_all_v3_masked, q_trained, test_df, rstats,
    )
    results["Random_uniform"] = run_policy(
        "Random_uniform", policy_random(rng_random), q_trained, test_df, rstats,
    )
    results["Oracle"] = run_policy(
        "Oracle", lambda q, r: policy_oracle(q, r, rstats),
        q_trained, test_df, rstats,
    )

    # ── Metrics + bootstrap ──
    print(f"[ml] bootstrap CI ({args.bootstrap})…")
    metrics: dict[str, dict] = {}
    for name, res in results.items():
        m = res.metrics()
        ci = bootstrap_ci(res.rewards, args.bootstrap, args.seed + hash(name) % 9999)
        m.update(ci)
        metrics[name] = m

    base_div = results["DIVERSIFY"].rewards
    base_v2 = results["ALL_V2"].rewards
    base_v3 = results["ALL_V3_masked"].rewards
    for name, res in results.items():
        metrics[name]["paired_t_vs_DIVERSIFY"] = paired_t(res.rewards, base_div)
        metrics[name]["paired_t_vs_ALL_V2"] = paired_t(res.rewards, base_v2)
        metrics[name]["paired_t_vs_ALL_V3_masked"] = paired_t(res.rewards, base_v3)

    # ── In-sample / OOS R² for ML models ──
    fit_diag = {}
    for name, model in [("Ridge", ridge_model), ("LightGBM", lgbm_model)]:
        diag = {"train_r2": {}, "test_r2": {}, "feature_importance": model.feature_importance()}
        Xtr, Xte = train_df[FEATURES].values, test_df[FEATURES].values
        for tgt in ("pnl_v1", "pnl_v2", "pnl_v3"):
            ytr = train_df[tgt].values
            yte = test_df[tgt].values
            yhat_tr = model.models[tgt].predict(model.scaler.transform(Xtr))
            yhat_te = model.models[tgt].predict(model.scaler.transform(Xte))
            ss_res_tr = float(np.sum((ytr - yhat_tr) ** 2))
            ss_tot_tr = float(np.sum((ytr - ytr.mean()) ** 2))
            ss_res_te = float(np.sum((yte - yhat_te) ** 2))
            ss_tot_te = float(np.sum((yte - yte.mean()) ** 2))
            diag["train_r2"][tgt] = 1 - ss_res_tr / max(ss_tot_tr, 1e-12)
            diag["test_r2"][tgt] = 1 - ss_res_te / max(ss_tot_te, 1e-12)
        fit_diag[name] = diag

    # ── Summary print ──
    order = ["Ridge", "LightGBM", "TrainedQ_walkforward", "PretrainedQ_full90d",
             "DIVERSIFY", "ALL_V2", "ALL_V3_masked", "Random_uniform", "Oracle"]
    hdr = f"{'policy':<26} {'cum_R':>9} {'mean':>9} {'sharpe':>8} {'maxDD':>8} {'win%':>7} {'$pnl':>9}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for name in order:
        m = metrics[name]
        print(f"{name:<26} {m['cum_reward']:>9.3f} {m['mean_reward']:>9.4f} "
              f"{m['sharpe_sample']:>8.3f} {m['max_drawdown']:>8.3f} "
              f"{m['win_rate']*100:>6.1f}% {m['cum_dollar_pnl']:>9.2f}")

    print("\n[ml] paired t-test vs DIVERSIFY:")
    for name in order:
        if name == "DIVERSIFY":
            continue
        t = metrics[name]["paired_t_vs_DIVERSIFY"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else ""))
        print(f"  {name:<26} Δ={t['mean_diff']:+.4f} t={t['t']:+.3f} p={t['p_value']:.4f} {sig}")

    print("\n[ml] paired t-test vs ALL_V3_masked (the rule-based competitor):")
    for name in order:
        if name == "ALL_V3_masked":
            continue
        t = metrics[name]["paired_t_vs_ALL_V3_masked"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else ""))
        print(f"  {name:<26} Δ={t['mean_diff']:+.4f} t={t['t']:+.3f} p={t['p_value']:.4f} {sig}")

    print("\n[ml] OOS R² (test slice) — does the model generalize?")
    for name, diag in fit_diag.items():
        print(f"  {name}:")
        for tgt in ("pnl_v1", "pnl_v2", "pnl_v3"):
            print(f"    {tgt:<8}  train R²={diag['train_r2'][tgt]:+.3f}  "
                  f"test R²={diag['test_r2'][tgt]:+.3f}")

    print("\n[ml] feature importance (LightGBM):")
    for tgt, imp in fit_diag["LightGBM"]["feature_importance"].items():
        print(f"  {tgt}: {imp}")

    # ── Persist ──
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.time(),
        "seed": args.seed,
        "bootstrap_resamples": args.bootstrap,
        "split": {
            "n_total": n_total, "n_cal": len(cal_df),
            "n_train": len(train_df), "n_test": len(test_df),
            "cal_range": [str(cal_df['tick_ts'].iloc[0]), str(cal_df['tick_ts'].iloc[-1])],
            "train_range": [str(train_df['tick_ts'].iloc[0]), str(train_df['tick_ts'].iloc[-1])],
            "test_range": [str(test_df['tick_ts'].iloc[0]), str(test_df['tick_ts'].iloc[-1])],
        },
        "regime_thresholds": thresholds,
        "reward_stats": rstats.to_dict(),
        "policies": metrics,
        "fit_diagnostics": fit_diag,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\n[ml] wrote {OUT_JSON}")

    md = render_report(payload, metrics, fit_diag)
    OUT_REPORT.write_text(md, encoding="utf-8")
    print(f"[ml] wrote {OUT_REPORT}")
    return 0


def render_report(payload, metrics, fit_diag) -> str:
    L: list[str] = []
    L.append("# Capital Allocator — RL vs ML Bake-off")
    L.append("")
    L.append("**Generated**: " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["generated_at"])))
    L.append("")
    L.append("## 1. Why this report exists")
    L.append("")
    L.append("Original design used tabular Q-learning. A DS critique caught the framing error:")
    L.append("")
    L.append("> The setup is **not an MDP**. Our action does not affect next tick's vol/funding/kimchi/usdc")
    L.append("> (the market is much bigger than us), and the cadence is 8h. Reframed honestly, this is a")
    L.append("> **contextual bandit** — which collapses to supervised regression: predict per-strategy")
    L.append("> expected pnl from current features, then argmax expected reward over 7 actions.")
    L.append("")
    L.append("This report runs Ridge regression and LightGBM on the **identical** walk-forward split and")
    L.append("compares them to the Q-table on the **identical** test slice with the **identical** reward")
    L.append("function. Whichever policy generalizes better wins.")
    L.append("")
    L.append("## 2. Hold-out split")
    L.append("")
    s = payload["split"]
    L.append(f"- **Cal** (μ/σ + thresholds): {s['n_cal']} ticks · {s['cal_range'][0]} → {s['cal_range'][1]}")
    L.append(f"- **Train** (model fit / Q-learning): {s['n_train']} ticks · {s['train_range'][0]} → {s['train_range'][1]}")
    L.append(f"- **Test** (frozen, never seen): {s['n_test']} ticks · {s['test_range'][0]} → {s['test_range'][1]}")
    L.append("")
    L.append("## 3. Headline metrics")
    L.append("")
    L.append("| Policy | Cum R | Mean R | Sharpe | Max DD | Win% | Cum $ PnL |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    order = ["Ridge", "LightGBM", "TrainedQ_walkforward", "PretrainedQ_full90d",
             "DIVERSIFY", "ALL_V2", "ALL_V3_masked", "Random_uniform", "Oracle"]
    for name in order:
        m = metrics[name]
        L.append(f"| **{name}** | {m['cum_reward']:.3f} | {m['mean_reward']:+.4f} | "
                 f"{m['sharpe_sample']:.3f} | {m['max_drawdown']:.3f} | "
                 f"{m['win_rate']*100:.1f}% | {m['cum_dollar_pnl']:+.2f} |")
    L.append("")
    L.append("## 4. Bootstrap 95% CI (mean reward)")
    L.append("")
    L.append("| Policy | mean R 95% CI | Sharpe 95% CI |")
    L.append("|---|---|---|")
    for name in order:
        m = metrics[name]
        L.append(f"| {name} | [{m['mean_lo']:+.4f}, {m['mean_hi']:+.4f}] | "
                 f"[{m['sharpe_lo']:.3f}, {m['sharpe_hi']:.3f}] |")
    L.append("")
    L.append("## 5. Statistical sanity (paired t-test on per-tick reward delta)")
    L.append("")
    L.append("`***` p<0.001, `**` p<0.01, `*` p<0.05, `n.s.` otherwise.")
    L.append("")
    L.append("### vs DIVERSIFY (the \"learn nothing\" baseline)")
    L.append("")
    L.append("| Policy | Δmean | t | p |")
    L.append("|---|---:|---:|---|")
    for name in order:
        if name == "DIVERSIFY":
            continue
        t = metrics[name]["paired_t_vs_DIVERSIFY"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else "n.s."))
        L.append(f"| {name} | {t['mean_diff']:+.4f} | {t['t']:+.3f} | {t['p_value']:.4f} {sig} |")
    L.append("")
    L.append("### vs ALL_V3_masked (the strongest rule-based competitor)")
    L.append("")
    L.append("| Policy | Δmean | t | p |")
    L.append("|---|---:|---:|---:|")
    for name in order:
        if name == "ALL_V3_masked":
            continue
        t = metrics[name]["paired_t_vs_ALL_V3_masked"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else "n.s."))
        L.append(f"| {name} | {t['mean_diff']:+.4f} | {t['t']:+.3f} | {t['p_value']:.4f} {sig} |")
    L.append("")
    L.append("## 6. ML model fit diagnostics")
    L.append("")
    L.append("In-sample vs out-of-sample R² for each per-strategy regressor.")
    L.append("Negative test R² means the model predicts worse than the test mean — overfit signal.")
    L.append("")
    for name, diag in fit_diag.items():
        L.append(f"### {name}")
        L.append("")
        L.append("| target | train R² | test R² |")
        L.append("|---|---:|---:|")
        for tgt in ("pnl_v1", "pnl_v2", "pnl_v3"):
            L.append(f"| {tgt} | {diag['train_r2'][tgt]:+.3f} | {diag['test_r2'][tgt]:+.3f} |")
        L.append("")
        L.append("**Feature importance / coefficient:**")
        L.append("")
        L.append("| target | " + " | ".join(FEATURES) + " |")
        L.append("|---|" + "|".join(["---:"] * len(FEATURES)) + "|")
        for tgt, imp in diag["feature_importance"].items():
            row = " | ".join(f"{imp[f]:+.3f}" for f in FEATURES)
            L.append(f"| {tgt} | {row} |")
        L.append("")
    L.append("## 7. Action distribution (test slice)")
    L.append("")
    for name in order:
        L.append(f"- **{name}**: {metrics[name]['action_distribution']}")
    L.append("")
    L.append("## 8. Read-out — which model should ship?")
    L.append("")
    L.append("Decision rule, in priority order:")
    L.append("")
    L.append("1. **Significantly beats DIVERSIFY (p < 0.05)**? If only one of {Ridge, LightGBM, TrainedQ}")
    L.append("   passes this gate, that's the recommendation.")
    L.append("2. **Significantly beats ALL_V3_masked**? If a learned model can't beat a 1-line rule,")
    L.append("   ship the rule.")
    L.append("3. **Test R² > 0** for at least one strategy? If both Ridge and LightGBM produce negative")
    L.append("   test R² across all three pnl targets, the features are noise on this slice.")
    L.append("4. **Pick the lowest-variance winner** — ties go to Ridge over LightGBM (smaller, more")
    L.append("   interpretable, easier to ship).")
    L.append("")
    L.append("## 9. Caveats — what these numbers do NOT cover")
    L.append("")
    L.append("- Same v1=synthetic AR(1) and v2=bootstrap-resampled limitations as `BACKTEST_REPORT.md` §7.")
    L.append("- Train slice is **46 ticks** — borderline for LightGBM. Negative test R² is expected on small data.")
    L.append("- No transaction-cost drag in `reward_fn` — production must subtract fees per leg.")
    L.append("- No regime-shift stress test (e.g. Mar→Apr funding regime change). 47 test ticks ≈ 15 days.")
    L.append("- Ridge / LGBM use the SAME 4 binned features the Q-table sees — fair competitor, but ")
    L.append("  not the only feature set possible. A richer feature build (lag-k funding, vol-of-vol, ")
    L.append("  cross-strategy correlation) might widen the gap.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
