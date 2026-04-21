"""Walk-forward back-test of the Capital Allocator Q-policy.

Hold-out split (no leakage):
    cal:   ticks [0   : 180]   — 60d, thresholds + reward stats
    train: ticks [180 : 225]   — 15d, Q-learning with UCB1 exploration
    test:  ticks [225 : end]   — ~15d, FROZEN Q greedy evaluation

Compares 7 policies on the test slice:
    1. Trained Q (greedy on frozen Q-table, capability-masked)
    2. Pretrained Q (loaded from consumers/capital_allocator/allocator_q.json)
    3. DIVERSIFY (1/3 each, every tick)
    4. ALL_V2 (single corner — most stable)
    5. ALL_V3 capability-aware (V3 if funding hot else DIVERSIFY)
    6. Random uniform (over capability-masked actions)
    7. Oracle (per-tick ex-post argmax — upper bound)

Metrics per policy:
    cumulative_reward, mean, std, sharpe (sample),
    max_drawdown, win_rate, action_entropy,
    cumulative_dollar_pnl (sum of dollar component, before z blend)

Statistical sanity:
    Bootstrap 1000x over test ticks → 95% CI for mean reward + sharpe.
    Paired t-test trained vs DIVERSIFY (and vs ALL_V2) → p-value.

CAVEATS (also printed in report):
    v1 PnL is synthetic AR(1) — any policy weighing v1 heavily has a noise
    component. v2 PnL is bootstrap-resampled from real 30d 1s pool — i.i.d.
    in time. Only v3 PnL is genuine 8h time-series. Trust ranking accordingly.

CLI:
    python scripts/backtest_allocator.py
    python scripts/backtest_allocator.py --bootstrap 2000 --seed 17
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd
from scipy import stats as sstats

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import regime_features as rf  # noqa: E402
from scripts.pretrain_allocator_q import (  # noqa: E402
    ACTIONS, ACTION_LABELS, ALPHA, LAMBDA, NUM_ACTIONS, NUM_STATES, Q_INIT,
    UCB_C, RewardStats, apply_capability_mask, calibrate_regime_thresholds,
    calibrate_reward_stats, load_funding_timeline, load_v2_dual_quote_8h_bins,
    build_v3_pnl_per_symbol_per_tick, reward_fn, synthesize_regime_features,
    synthesize_v1_pnl,
)

CORNER = {0, 1, 2}
DIVERSIFY_IDX = 6
ALL_V2_IDX = 1
ALL_V3_IDX = 2

OUT_REPORT = ROOT / "docs" / "BACKTEST_REPORT.md"
OUT_JSON = ROOT / "docs" / "backtest_metrics.json"


# ─────────────────────────────────────────────────────────────────────────
# Data assembly (mirror pretrain to guarantee identical timeline)
# ─────────────────────────────────────────────────────────────────────────
def build_timeline(seed: int = 42) -> pd.DataFrame:
    funding = load_funding_timeline()
    funding = build_v3_pnl_per_symbol_per_tick(funding)
    v3_per_tick = funding.groupby("tick_ts")["pnl_v3"].mean().sort_index()
    features = synthesize_regime_features(funding, seed=seed + 1)
    features = features.set_index("tick_ts").reindex(v3_per_tick.index)

    v2_pool = load_v2_dual_quote_8h_bins()
    rng_v2 = np.random.default_rng(seed + 2)
    v2_per_tick = np.array([rng_v2.choice(v2_pool) for _ in range(len(v3_per_tick))])
    v1_per_tick = synthesize_v1_pnl(len(v3_per_tick), seed=seed + 3)

    timeline = pd.DataFrame({
        "tick_ts": v3_per_tick.index,
        "pnl_v1": v1_per_tick,
        "pnl_v2": v2_per_tick,
        "pnl_v3": v3_per_tick.values,
        "vol": features["vol"].values,
        "funding_median": features["funding_median"].values,
        "kimchi_premium": features["kimchi_premium"].values,
        "usdc_spread": features["usdc_spread"].values,
    }).dropna().reset_index(drop=True)
    return timeline


# ─────────────────────────────────────────────────────────────────────────
# Q-learning train (UCB1 over enumerated actions)
# ─────────────────────────────────────────────────────────────────────────
def train_q(train_df: pd.DataFrame, stats: RewardStats, seed: int = 42) -> tuple[list, list]:
    """Online UCB1 Q-learning on train slice. Returns (q_table, visits)."""
    q = [[Q_INIT] * NUM_ACTIONS for _ in range(NUM_STATES)]
    n = [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]
    rng = np.random.default_rng(seed + 100)
    # Walk train ticks in sequence; use UCB1 to pick action; TD update.
    for _, row in train_df.iterrows():
        s = rf.state_index(
            float(row["vol"]), float(row["funding_median"]),
            float(row["kimchi_premium"]), float(row["usdc_spread"]),
        )
        funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
        # UCB1 score per action
        total_n = sum(n[s]) + 1
        log_t = math.log(total_n)
        best_a, best_score = -1, -math.inf
        for a in range(NUM_ACTIONS):
            if not apply_capability_mask(a, funding_bit):
                continue
            bonus = UCB_C * math.sqrt(log_t / (n[s][a] + 1))
            score = q[s][a] + bonus
            if score > best_score:
                best_score = score
                best_a = a
        if best_a < 0:
            best_a = DIVERSIFY_IDX
        r = reward_fn(best_a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], stats)
        q[s][best_a] += ALPHA * (r - q[s][best_a])
        n[s][best_a] += 1
    return q, n


# ─────────────────────────────────────────────────────────────────────────
# Policy implementations — each returns action_idx given a row
# ─────────────────────────────────────────────────────────────────────────
def policy_q_greedy(q: list, row: pd.Series) -> int:
    s = rf.state_index(
        float(row["vol"]), float(row["funding_median"]),
        float(row["kimchi_premium"]), float(row["usdc_spread"]),
    )
    funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
    best_a, best_q = -1, -math.inf
    for a in range(NUM_ACTIONS):
        if not apply_capability_mask(a, funding_bit):
            continue
        if q[s][a] > best_q:
            best_q = q[s][a]
            best_a = a
    return best_a if best_a >= 0 else DIVERSIFY_IDX


def policy_diversify(_q, _row) -> int:
    return DIVERSIFY_IDX


def policy_all_v2(_q, _row) -> int:
    return ALL_V2_IDX


def policy_all_v3_masked(_q, row: pd.Series) -> int:
    funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
    return ALL_V3_IDX if funding_bit == 1 else DIVERSIFY_IDX


def policy_random(rng: np.random.Generator):
    def _pick(_q, row):
        funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
        choices = [a for a in range(NUM_ACTIONS) if apply_capability_mask(a, funding_bit)]
        return int(rng.choice(choices))
    return _pick


def policy_oracle(_q, row, stats):
    funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
    best_a, best_r = -1, -math.inf
    for a in range(NUM_ACTIONS):
        if not apply_capability_mask(a, funding_bit):
            continue
        r = reward_fn(a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], stats)
        if r > best_r:
            best_r = r
            best_a = a
    return best_a if best_a >= 0 else DIVERSIFY_IDX


# ─────────────────────────────────────────────────────────────────────────
# Evaluation
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class PolicyResult:
    name: str
    rewards: np.ndarray         # per-tick blended reward
    dollar_pnls: np.ndarray     # per-tick raw dollar pnl
    actions: list[int]

    def cumulative(self) -> np.ndarray:
        return np.cumsum(self.rewards)

    def cumulative_dollar(self) -> np.ndarray:
        return np.cumsum(self.dollar_pnls)

    def metrics(self) -> dict:
        r = self.rewards
        n = len(r)
        mean_r = float(np.mean(r))
        std_r = float(np.std(r, ddof=1)) if n > 1 else 0.0
        sharpe = mean_r / std_r * math.sqrt(n) if std_r > 1e-9 else 0.0
        cum = self.cumulative()
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        max_dd = float(np.max(dd))
        win_rate = float(np.mean(r > 0))
        # Action entropy
        cnt = Counter(self.actions)
        probs = np.array([v / n for v in cnt.values()])
        entropy = float(-(probs * np.log(probs + 1e-12)).sum()) if n > 0 else 0.0
        return {
            "n_ticks": n,
            "mean_reward": mean_r,
            "std_reward": std_r,
            "cum_reward": float(cum[-1]) if n else 0.0,
            "cum_dollar_pnl": float(self.cumulative_dollar()[-1]) if n else 0.0,
            "sharpe_sample": sharpe,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "action_entropy": entropy,
            "action_distribution": {ACTION_LABELS[a]: c for a, c in cnt.most_common()},
        }


def run_policy(name: str, picker, q: list, test_df: pd.DataFrame, stats: RewardStats) -> PolicyResult:
    rewards, dollars, actions = [], [], []
    for _, row in test_df.iterrows():
        a = picker(q, row)
        actions.append(a)
        r = reward_fn(a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], stats)
        w1, w2, w3 = ACTIONS[a]
        d = w1 * row["pnl_v1"] + w2 * row["pnl_v2"] + w3 * row["pnl_v3"]
        rewards.append(r)
        dollars.append(d)
    return PolicyResult(name, np.array(rewards), np.array(dollars), actions)


def bootstrap_ci(values: np.ndarray, n_resample: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = len(values)
    if n == 0:
        return {"mean_lo": 0.0, "mean_hi": 0.0, "sharpe_lo": 0.0, "sharpe_hi": 0.0}
    means = np.empty(n_resample)
    sharpes = np.empty(n_resample)
    for i in range(n_resample):
        sample = values[rng.integers(0, n, n)]
        means[i] = sample.mean()
        sd = sample.std(ddof=1) if n > 1 else 0.0
        sharpes[i] = sample.mean() / sd * math.sqrt(n) if sd > 1e-9 else 0.0
    return {
        "mean_lo": float(np.percentile(means, 2.5)),
        "mean_hi": float(np.percentile(means, 97.5)),
        "sharpe_lo": float(np.percentile(sharpes, 2.5)),
        "sharpe_hi": float(np.percentile(sharpes, 97.5)),
    }


def paired_t(a: np.ndarray, b: np.ndarray) -> dict:
    diff = a - b
    if len(diff) < 2:
        return {"mean_diff": 0.0, "t": 0.0, "p_value": 1.0}
    t_stat, p_val = sstats.ttest_rel(a, b)
    return {
        "mean_diff": float(diff.mean()),
        "t": float(t_stat),
        "p_value": float(p_val),
    }


# ─────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--cal-end-pct", type=float, default=0.66,
                    help="fraction of timeline used as calibration window")
    ap.add_argument("--train-end-pct", type=float, default=0.83,
                    help="fraction of timeline that ends the train window")
    args = ap.parse_args()

    print("[bt] building timeline…")
    tl = build_timeline(seed=args.seed)
    n_total = len(tl)
    cal_end = int(n_total * args.cal_end_pct)
    train_end = int(n_total * args.train_end_pct)
    cal_df = tl.iloc[:cal_end].reset_index(drop=True)
    train_df = tl.iloc[cal_end:train_end].reset_index(drop=True)
    test_df = tl.iloc[train_end:].reset_index(drop=True)
    print(f"[bt] timeline n={n_total}, cal={len(cal_df)}, train={len(train_df)}, test={len(test_df)}")
    print(f"[bt] cal range  : {cal_df['tick_ts'].iloc[0]} → {cal_df['tick_ts'].iloc[-1]}")
    print(f"[bt] train range: {train_df['tick_ts'].iloc[0]} → {train_df['tick_ts'].iloc[-1]}")
    print(f"[bt] test range : {test_df['tick_ts'].iloc[0]} → {test_df['tick_ts'].iloc[-1]}")

    # Calibrate thresholds + reward stats on cal slice
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
    print(f"[bt] thresholds : {thresholds}")

    rstats = calibrate_reward_stats(
        cal_df["pnl_v1"].values, cal_df["pnl_v2"].values, cal_df["pnl_v3"].values
    )
    print(f"[bt] reward stats: μ_v1={rstats.mu_v1:+.3f} σ_v1={rstats.sigma_v1:.3f} "
          f"μ_v2={rstats.mu_v2:+.3f} σ_v2={rstats.sigma_v2:.3f} "
          f"μ_v3={rstats.mu_v3:+.3f} σ_v3={rstats.sigma_v3:.3f} D={rstats.dollar_scale:.3f}")

    # Train Q on train slice
    print(f"[bt] training Q on {len(train_df)} ticks (UCB1 online)…")
    q_trained, visits_trained = train_q(train_df, rstats, seed=args.seed)

    # Load pretrained Q
    pretrained_path = ROOT / "consumers" / "capital_allocator" / "allocator_q.json"
    pretrained = json.loads(pretrained_path.read_text(encoding="utf-8"))
    q_pretrained = pretrained["q_table"]

    # Run all policies on test slice
    print(f"[bt] evaluating policies on {len(test_df)} test ticks…")
    rng_random = np.random.default_rng(args.seed + 200)
    results: dict[str, PolicyResult] = {}
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

    # Metrics + bootstrap
    print(f"[bt] bootstrap CI ({args.bootstrap} resamples)…")
    metrics: dict[str, dict] = {}
    for name, res in results.items():
        m = res.metrics()
        ci = bootstrap_ci(res.rewards, args.bootstrap, args.seed + hash(name) % 9999)
        m.update(ci)
        metrics[name] = m

    # Stat tests vs DIVERSIFY and ALL_V2
    base_div = results["DIVERSIFY"].rewards
    base_v2 = results["ALL_V2"].rewards
    for name, res in results.items():
        if name in ("DIVERSIFY",):
            continue
        metrics[name]["paired_t_vs_DIVERSIFY"] = paired_t(res.rewards, base_div)
    for name, res in results.items():
        if name in ("ALL_V2",):
            continue
        metrics[name]["paired_t_vs_ALL_V2"] = paired_t(res.rewards, base_v2)

    # ── Print summary table ──
    hdr = f"{'policy':<26} {'cum_R':>9} {'mean':>9} {'sharpe':>8} {'maxDD':>8} {'win%':>7} {'H_act':>7} {'$pnl':>9}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for name, m in metrics.items():
        print(f"{name:<26} {m['cum_reward']:>9.3f} {m['mean_reward']:>9.4f} "
              f"{m['sharpe_sample']:>8.3f} {m['max_drawdown']:>8.3f} "
              f"{m['win_rate']*100:>6.1f}% {m['action_entropy']:>7.3f} "
              f"{m['cum_dollar_pnl']:>9.2f}")

    print("\n[bt] paired t-test vs DIVERSIFY:")
    for name in ("TrainedQ_walkforward", "PretrainedQ_full90d", "ALL_V2", "ALL_V3_masked", "Random_uniform", "Oracle"):
        t = metrics[name]["paired_t_vs_DIVERSIFY"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else ""))
        print(f"  {name:<26} Δmean={t['mean_diff']:+.4f}  t={t['t']:+.3f}  p={t['p_value']:.4f} {sig}")

    print("\n[bt] paired t-test vs ALL_V2:")
    for name in ("TrainedQ_walkforward", "PretrainedQ_full90d", "DIVERSIFY", "ALL_V3_masked", "Random_uniform", "Oracle"):
        t = metrics[name]["paired_t_vs_ALL_V2"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else ""))
        print(f"  {name:<26} Δmean={t['mean_diff']:+.4f}  t={t['t']:+.3f}  p={t['p_value']:.4f} {sig}")

    # ── Persist ──
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.time(),
        "seed": args.seed,
        "bootstrap_resamples": args.bootstrap,
        "split": {
            "n_total": n_total, "n_cal": len(cal_df), "n_train": len(train_df), "n_test": len(test_df),
            "cal_range": [str(cal_df['tick_ts'].iloc[0]), str(cal_df['tick_ts'].iloc[-1])],
            "train_range": [str(train_df['tick_ts'].iloc[0]), str(train_df['tick_ts'].iloc[-1])],
            "test_range": [str(test_df['tick_ts'].iloc[0]), str(test_df['tick_ts'].iloc[-1])],
        },
        "regime_thresholds": thresholds,
        "reward_stats": rstats.to_dict(),
        "policies": metrics,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\n[bt] wrote {OUT_JSON}")

    # ── Markdown report ──
    md = render_report(payload, metrics)
    OUT_REPORT.write_text(md, encoding="utf-8")
    print(f"[bt] wrote {OUT_REPORT}")
    return 0


def render_report(payload: dict, metrics: dict) -> str:
    L: list[str] = []
    L.append("# Capital Allocator — Walk-forward Back-test Report")
    L.append("")
    L.append("**Generated**: " + time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["generated_at"])))
    L.append("")
    L.append("## 1. Hold-out split (no leakage)")
    s = payload["split"]
    L.append(f"- Total ticks (8h cadence, 5 coins): **{s['n_total']}**")
    L.append(f"- **Cal** (thresholds + reward μ/σ): {s['n_cal']} ticks · {s['cal_range'][0]} → {s['cal_range'][1]}")
    L.append(f"- **Train** (UCB1 Q-learning): {s['n_train']} ticks · {s['train_range'][0]} → {s['train_range'][1]}")
    L.append(f"- **Test** (frozen Q greedy): {s['n_test']} ticks · {s['test_range'][0]} → {s['test_range'][1]}")
    L.append("")
    L.append("All metrics below are computed on the **test slice only** — the policies never see these ticks during training.")
    L.append("")
    L.append("## 2. Policies compared")
    L.append("")
    L.append("| # | Policy | Description |")
    L.append("|---|--------|-------------|")
    L.append("| 1 | TrainedQ_walkforward | Q-table learned on the train slice with UCB1, then frozen and run greedy on test |")
    L.append("| 2 | PretrainedQ_full90d  | The shipped Q-table from `consumers/capital_allocator/allocator_q.json` (trained on full timeline) — **leakage check**: should ≥ TrainedQ_walkforward |")
    L.append("| 3 | DIVERSIFY            | Constant 1/3 × (v1, v2, v3). \"I don't know\" baseline |")
    L.append("| 4 | ALL_V2               | Constant 100% v2 (most stable corner) |")
    L.append("| 5 | ALL_V3_masked        | 100% v3 when funding hot, else DIVERSIFY |")
    L.append("| 6 | Random_uniform       | Uniform random over capability-masked actions |")
    L.append("| 7 | Oracle               | Per-tick ex-post argmax — **upper bound**, not achievable in production |")
    L.append("")
    L.append("## 3. Headline metrics")
    L.append("")
    L.append("| Policy | Cum R | Mean R | Sharpe | Max DD | Win% | H(act) | Cum $ PnL |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    order = ["TrainedQ_walkforward", "PretrainedQ_full90d", "DIVERSIFY", "ALL_V2",
             "ALL_V3_masked", "Random_uniform", "Oracle"]
    for name in order:
        m = metrics[name]
        L.append(f"| {name} | {m['cum_reward']:.3f} | {m['mean_reward']:+.4f} | "
                 f"{m['sharpe_sample']:.3f} | {m['max_drawdown']:.3f} | "
                 f"{m['win_rate']*100:.1f}% | {m['action_entropy']:.3f} | "
                 f"{m['cum_dollar_pnl']:+.2f} |")
    L.append("")
    L.append("**Reward** is the design §3.2 blend: 0.8·z-score + 0.2·dollar/scale. **Cum $ PnL** is raw dollars (interpretable but smaller — it's the bit before z-blending). **Sharpe** here is the sample-period Sharpe (no annualization, since 46 ticks ≈ 15 days).")
    L.append("")
    L.append("## 4. Bootstrap 95% CI (mean reward + Sharpe)")
    L.append("")
    L.append(f"_{payload['bootstrap_resamples']} resamples with replacement over test ticks._")
    L.append("")
    L.append("| Policy | mean R 95% CI | Sharpe 95% CI |")
    L.append("|---|---|---|")
    for name in order:
        m = metrics[name]
        L.append(f"| {name} | [{m['mean_lo']:+.4f}, {m['mean_hi']:+.4f}] | "
                 f"[{m['sharpe_lo']:.3f}, {m['sharpe_hi']:.3f}] |")
    L.append("")
    L.append("## 5. Statistical sanity (paired t-test)")
    L.append("")
    L.append("Tests whether the per-tick reward delta differs from zero. p < 0.05 = `*`, < 0.01 = `**`, < 0.001 = `***`.")
    L.append("")
    L.append("### vs DIVERSIFY (the \"learn nothing\" baseline)")
    L.append("")
    L.append("| Policy | Δmean | t | p |")
    L.append("|---|---:|---:|---:|")
    for name in ["TrainedQ_walkforward", "PretrainedQ_full90d", "ALL_V2",
                 "ALL_V3_masked", "Random_uniform", "Oracle"]:
        t = metrics[name]["paired_t_vs_DIVERSIFY"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else "n.s."))
        L.append(f"| {name} | {t['mean_diff']:+.4f} | {t['t']:+.3f} | {t['p_value']:.4f} {sig} |")
    L.append("")
    L.append("### vs ALL_V2 (the strongest corner baseline)")
    L.append("")
    L.append("| Policy | Δmean | t | p |")
    L.append("|---|---:|---:|---:|")
    for name in ["TrainedQ_walkforward", "PretrainedQ_full90d", "DIVERSIFY",
                 "ALL_V3_masked", "Random_uniform", "Oracle"]:
        t = metrics[name]["paired_t_vs_ALL_V2"]
        sig = "***" if t["p_value"] < 0.001 else ("**" if t["p_value"] < 0.01 else ("*" if t["p_value"] < 0.05 else "n.s."))
        L.append(f"| {name} | {t['mean_diff']:+.4f} | {t['t']:+.3f} | {t['p_value']:.4f} {sig} |")
    L.append("")
    L.append("## 6. Action distribution (how each policy behaved on test)")
    L.append("")
    for name in order:
        L.append(f"- **{name}**: {metrics[name]['action_distribution']}")
    L.append("")
    L.append("## 7. Caveats — what these numbers do and DO NOT prove")
    L.append("")
    L.append("**What's real**:")
    L.append("- Funding rates + perp_close + spot_close: 90 days of actual Binance fapi data (5 majors).")
    L.append("- v3 PnL formula: `funding_rate × $500 + basis_change × $250` — derived from those real series.")
    L.append("- Regime features `vol` + `funding_median`: real (vol is rolling-8 σ of cross-sectional perp returns).")
    L.append("")
    L.append("**What's synthetic / approximated** — affects how to read the table:")
    L.append("- **v1 PnL is AR(1) φ=0.4 σ=$0.80** — Upbit/kimchi data not in this repo. So any policy whose alpha comes from v1 (notably ALL_V1) is reading noise. The v1 column in the action distribution is a red flag.")
    L.append("- **v2 PnL is bootstrap-resampled** from a real 30-day 1s pool of Binance USDT/USDC premium — i.i.d. in time, no autocorrelation. So Sharpe of an ALL_V2 policy is upward-biased vs reality.")
    L.append("- **kimchi_premium + usdc_spread features are synthetic AR(1)** — used as state inputs only, not PnL inputs. They affect which Q cells get visited but don't fake reward.")
    L.append("")
    L.append("**Trustworthy comparisons**:")
    L.append("- TrainedQ vs DIVERSIFY → tests whether **state-conditioning helps at all**.")
    L.append("- TrainedQ vs ALL_V3_masked → tests whether **the multi-strategy mix beats the strongest single-corner**.")
    L.append("- TrainedQ vs Oracle → measures **regret** (the unrecoverable gap to ex-post optimal).")
    L.append("")
    L.append("**Less trustworthy**:")
    L.append("- TrainedQ vs ALL_V2 → biased by v2's i.i.d. resampling. Treat as a sanity floor, not a real beat.")
    L.append("")
    L.append("## 8. What would make this report honest in production")
    L.append("- Wire actual Upbit kimchi parquet → kill the v1 AR(1) and re-run.")
    L.append("- Replace v2 bootstrap with chronologically-aligned 8h dual_quote bins (need 90d 1s data, not 30d).")
    L.append("- Add k-fold walk-forward (k=3) once data is real to detect regime instability.")
    L.append("- Add transaction-cost drag to reward_fn (currently $0 — a real allocator pays Bybit VIP0 0.05%/leg + funding-side-spread + USDC settlement).")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
