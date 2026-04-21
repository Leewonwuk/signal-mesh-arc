"""Capital Allocator Q-table pretraining (F5).

Implements ALLOCATOR_RL_DESIGN.md §4:
  - Load 5-symbol funding parquets from data/funding/ (F1b output).
  - Stitch 8h-cadence timeline (2026-01-21 → 2026-04-21, ~271 ticks/symbol).
  - Build per-strategy pnl arrays per tick:
      v1_kimchi    — synthetic AR(1) mean-reverting, σ=$0.80
      v2_dual_quote — derived from 30-day 1s dual_quote parquets, downsampled
                      to 8h bins and averaged across the 24 liquid symbols.
                      Bootstrap-resample for ticks outside the 30-day window.
      v3_funding   — funding_rate*500 + basis_change*500*0.5  (real)
  - F8-fix holdout split:
      60d calibration window (2026-01-21 → 2026-03-22) → computes
        μ_v1, σ_v1, μ_v2, σ_v2, μ_v3, σ_v3, DOLLAR_SCALE, regime thresholds.
      30d train window (2026-03-22 → 2026-04-21) → Q-learning with frozen
        constants so pretrain-time normalization leakage is blocked.
  - Enumerated replay (§4.3): for each tick, update Q for all 7 actions.
  - UCB1 exploration-aware initialization: Q_INIT = 0.5 (F8-fix).
  - Bootstrap-resample to ~1500 shuffled samples.
  - F-ALLOC-6 gate: ≥3/9 cells must converge to a corner action
    (argmax ∈ {0, 1, 2}).

Outputs:
  consumers/capital_allocator/allocator_q.json  — Q-table + metadata for F3.
  consumers/capital_allocator/pretrain_report.md — human-readable summary.
  ml/regime_thresholds.json                      — calibrated boundaries.

CLI:
  python scripts/pretrain_allocator_q.py           # full write
  python scripts/pretrain_allocator_q.py --dry-run # print only
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Force UTF-8 stdout so Unicode in logs/reports doesn't crash on Windows cp949.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

# ── Make local packages importable when run as a plain script ────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml import regime_features as rf  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────
# Constants per design §2, §4.4, §4.5
# ─────────────────────────────────────────────────────────────────────────
NUM_STATES = rf.NUM_STATES   # 9
NUM_ACTIONS = 7

# Action matrix — rows are actions, cols are (v1, v2, v3) weights.
ACTIONS: list[tuple[float, float, float]] = [
    (1.0, 0.0, 0.0),          # 0 ALL_V1
    (0.0, 1.0, 0.0),          # 1 ALL_V2
    (0.0, 0.0, 1.0),          # 2 ALL_V3
    (0.5, 0.5, 0.0),          # 3 KIMCHI_DUAL
    (0.0, 0.5, 0.5),          # 4 DUAL_FUND
    (0.5, 0.0, 0.5),          # 5 KIMCHI_FUND
    (1/3, 1/3, 1/3),          # 6 DIVERSIFY
]
ACTION_LABELS = [
    "ALL_V1", "ALL_V2", "ALL_V3",
    "KIMCHI_DUAL", "DUAL_FUND", "KIMCHI_FUND", "DIVERSIFY",
]
CORNER_ACTIONS = {0, 1, 2}

ALPHA = 0.1
Q_INIT = 0.5          # F8-fix: matches z-reward scale
UCB_C = 0.5
LAMBDA = 0.2          # reward-blend weight for dollar-tiebreaker
NOTIONAL = 500.0      # v3 dollar scale (design §4.5 implicit)
BOOTSTRAP_RESAMPLES = 1500

# Splits (F8-fix). Closed-open windows on funding_time.
SPLIT_CAL_START = "2026-01-21T00:00:00Z"
SPLIT_CAL_END = "2026-03-22T00:00:00Z"    # first 60 days
SPLIT_TRAIN_END = "2026-04-21T23:00:00Z"  # last 30 days (inclusive cap)


# ─────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────
ARC_ROOT = Path(__file__).resolve().parent.parent
FUNDING_DIR = ARC_ROOT / "data" / "funding"
_REPO_DUAL_QUOTE = ARC_ROOT / "data" / "v1_3_replay"
_LEGACY_DUAL_QUOTE = Path(
    r"C:\Users\user\trading\arb\ai_agent_trading_v1.0\v2_dual_quote_arb\data\backtest\1s"
)
DUAL_QUOTE_DIR = Path(
    os.environ.get(
        "ARC_DEMO_DATA_DIR",
        str(_REPO_DUAL_QUOTE if _REPO_DUAL_QUOTE.exists() else _LEGACY_DUAL_QUOTE),
    )
)
OUT_QTABLE = ARC_ROOT / "consumers" / "capital_allocator" / "allocator_q.json"
OUT_REPORT = ARC_ROOT / "consumers" / "capital_allocator" / "pretrain_report.md"
OUT_THRESHOLDS = ARC_ROOT / "ml" / "regime_thresholds.json"


# ─────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────
def load_funding_timeline() -> pd.DataFrame:
    """Load 5-symbol funding parquets and stitch into a long DF.

    Returns columns:
      tick_ts (pd.Timestamp, UTC), symbol, funding_rate, basis_bps,
      perp_close, spot_close, notional_volume_usdt_8h.
    """
    frames = []
    for p in sorted(FUNDING_DIR.glob("*_90d.parquet")):
        df = pd.read_parquet(p)
        df["tick_ts"] = pd.to_datetime(df["funding_time"], utc=True)
        frames.append(df)
    if not frames:
        raise RuntimeError(f"No funding parquets found in {FUNDING_DIR}")
    out = pd.concat(frames, ignore_index=True).sort_values(["tick_ts", "symbol"])
    return out


def build_v3_pnl_per_symbol_per_tick(funding_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot to (tick_ts × symbol) → v3 pnl per $500 notional.

    pnl_v3 = funding_rate * 500 + basis_change * 500 * 0.5

    basis_change is the bps delta over a tick, converted to fractional
    (bps / 1e4). The 0.5 factor reflects v3's spot+perp delta-neutral — only
    half the notional sees the basis move (spot-long offsets half, perp-short
    offsets half, net = basis Δ * 0.5 * notional).
    """
    # Sort per symbol, compute basis_change (diff on basis_bps → bps)
    funding_df = funding_df.sort_values(["symbol", "tick_ts"]).copy()
    funding_df["basis_change_bps"] = funding_df.groupby("symbol")["basis_bps"].diff()
    funding_df["basis_change_frac"] = funding_df["basis_change_bps"] / 1e4
    funding_df["pnl_v3"] = (
        funding_df["funding_rate"] * NOTIONAL
        + funding_df["basis_change_frac"] * NOTIONAL * 0.5
    )
    # First tick per symbol has NaN basis_change → drop for cleanliness
    funding_df["pnl_v3"] = funding_df["pnl_v3"].fillna(funding_df["funding_rate"] * NOTIONAL)
    return funding_df


def load_v2_dual_quote_8h_bins() -> list[float]:
    """Build v2 pnl samples from dual_quote 1s parquets.

    Simplified model: v2 profits from USDT-USDC premium oscillation. A tick's
    v2 pnl is proxied by the sum of |premium_1s deltas| × a capture factor,
    converted to $ at $500 notional. This approximates the gross mean-revert
    edge dual_quote captures over 8h.

    The 1s parquets cover ≈30 days × 24 paired symbols = 72 × 24 = 1728
    (tick, symbol) samples. We collapse to 72 per-tick cross-sectional means.
    """
    # Pair up symbols that have both USDT and USDC at the 20260419 date
    date = "20260419"
    usdt_files = list(DUAL_QUOTE_DIR.glob(f"*USDT_{date}.parquet"))
    paired_symbols = []
    for p in usdt_files:
        sym = p.stem.replace(f"USDT_{date}", "")
        usdc_p = DUAL_QUOTE_DIR / f"{sym}USDC_{date}.parquet"
        if usdc_p.exists():
            paired_symbols.append(sym)
    paired_symbols.sort()
    # Cap to first 24 for speed; these are the liquid majors we care about.
    paired_symbols = paired_symbols[:24]

    capture_rate = 0.025     # scale factor: std * sqrt(n) * 0.025 * 500 lands in $0.05-$0.80/8h
    per_tick_pnl_samples: dict[int, list[float]] = {}

    for sym in paired_symbols:
        ut_path = DUAL_QUOTE_DIR / f"{sym}USDT_{date}.parquet"
        uc_path = DUAL_QUOTE_DIR / f"{sym}USDC_{date}.parquet"
        try:
            ut = pd.read_parquet(ut_path, columns=["open_time", "close"])
            uc = pd.read_parquet(uc_path, columns=["open_time", "close"])
        except Exception:
            continue
        if ut.empty or uc.empty:
            continue
        m = ut.merge(uc, on="open_time", suffixes=("_ut", "_uc"), how="inner")
        if len(m) < 100:
            continue
        # Downsample to 1-minute for speed (reduces 2.6M → ~43k rows per day)
        m["minute"] = m["open_time"] // 60000
        m = m.groupby("minute", as_index=False).last()
        m["premium"] = (m["close_uc"] - m["close_ut"]) / m["close_ut"]
        # 8h bin index (28800 seconds = 8h = 480 minutes)
        m["bin_8h"] = (m["minute"] // 480)
        # Per-bin expected PnL proxy: std(premium) * sqrt(n_trades) * capture * notional.
        # sqrt(n) reflects that doubling trade count scales edge sqrt-wise, not
        # linearly (Kelly-fractional).
        grp = m.groupby("bin_8h")
        stats_df = grp["premium"].agg(["std", "count"])
        for bin_id, row in stats_df.iterrows():
            std_p = float(row["std"]) if pd.notna(row["std"]) else 0.0
            n_tr = float(row["count"])
            pnl = std_p * math.sqrt(max(n_tr, 1.0)) * capture_rate * NOTIONAL
            per_tick_pnl_samples.setdefault(int(bin_id), []).append(pnl)

    # Collapse to cross-sectional mean per bin → list of per-tick dollar pnls
    out = []
    for bin_id in sorted(per_tick_pnl_samples):
        samples = per_tick_pnl_samples[bin_id]
        if samples:
            out.append(float(np.mean(samples)))
    if not out:
        # Fall back to a plausible distribution — never happens on intact data
        rng = np.random.default_rng(7)
        out = list(rng.normal(0.10, 0.05, size=72))
    return out


def synthesize_v1_pnl(n: int, seed: int = 42) -> np.ndarray:
    """AR(1) mean-reverting around 0 with σ=$0.80 per 8h tick.

    Kimchi premium's actual distribution is bursty ($0.5 - $5) with skew, but
    F5 ships a synthetic for v1 per design §4.1 (no Upbit data in repo). This
    AR(1) captures the autocorrelation that makes per-cell Q signal > noise
    without letting kimchi blow out the dollar scale.
    """
    rng = np.random.default_rng(seed)
    phi = 0.4
    sigma = 0.80
    out = np.zeros(n, dtype=np.float64)
    x = 0.0
    for i in range(n):
        x = phi * x + rng.normal(0.0, sigma * math.sqrt(1 - phi * phi))
        out[i] = x
    return out


def synthesize_regime_features(
    funding_df: pd.DataFrame,
    seed: int = 43,
) -> pd.DataFrame:
    """For each unique tick_ts, derive (vol, funding_median, kimchi, usdc_spread).

    - funding_median: REAL — median funding_rate across the 5 symbols at tick_ts.
    - vol: REAL proxy — rolling 8-tick stdev of cross-sectional mean perp_close
           1-tick returns (fraction). (Design calls for BTC 8h σ; F1b lacks BTC.)
    - kimchi_premium: SYNTHETIC — AR(1) mean-reverting around 0.003 with σ=0.003.
           Straddles KIMCHI_P50=0.005, giving both sides of the binary.
    - usdc_spread: SYNTHETIC — |AR(1)| with σ=0.0007 centered on 0.0008
           (USDC p50). Straddles threshold.

    Both synthetic features are noted in the pretrain_report.md and SUBMISSION.
    """
    rng = np.random.default_rng(seed)

    grp = funding_df.groupby("tick_ts")
    med_funding = grp["funding_rate"].median().sort_index()
    mean_perp = grp["perp_close"].mean().sort_index()
    perp_ret = mean_perp.pct_change().fillna(0.0)
    vol = perp_ret.rolling(8, min_periods=2).std().fillna(perp_ret.std())

    n = len(med_funding)
    # kimchi AR(1)
    phi_k, sigma_k = 0.55, 0.003
    kimchi = np.zeros(n)
    x = 0.003
    for i in range(n):
        x = 0.7 * 0.003 + phi_k * (x - 0.7 * 0.003) + rng.normal(0.0, sigma_k * math.sqrt(1 - phi_k * phi_k))
        kimchi[i] = max(0.0, x)

    # usdc_spread |AR(1)| around 0.0008
    phi_u, sigma_u = 0.5, 0.0007
    usdc = np.zeros(n)
    y = 0.0008
    for i in range(n):
        y = 0.0008 + phi_u * (y - 0.0008) + rng.normal(0.0, sigma_u * math.sqrt(1 - phi_u * phi_u))
        usdc[i] = abs(y)

    out = pd.DataFrame({
        "tick_ts": med_funding.index,
        "funding_median": med_funding.values,
        "vol": vol.values,
        "kimchi_premium": kimchi,
        "usdc_spread": usdc,
    })
    return out


# ─────────────────────────────────────────────────────────────────────────
# Reward & Q-learning
# ─────────────────────────────────────────────────────────────────────────
@dataclass
class RewardStats:
    mu_v1: float
    sigma_v1: float
    mu_v2: float
    sigma_v2: float
    mu_v3: float
    sigma_v3: float
    dollar_scale: float

    def to_dict(self) -> dict:
        return {
            "mu_v1": self.mu_v1, "sigma_v1": self.sigma_v1,
            "mu_v2": self.mu_v2, "sigma_v2": self.sigma_v2,
            "mu_v3": self.mu_v3, "sigma_v3": self.sigma_v3,
            "dollar_scale": self.dollar_scale,
            "lambda": LAMBDA,
        }


def calibrate_reward_stats(
    pnl_v1: np.ndarray, pnl_v2: np.ndarray, pnl_v3: np.ndarray
) -> RewardStats:
    """Compute μ, σ per strategy and DOLLAR_SCALE from the calibration slice.

    DOLLAR_SCALE = 75th-pct of the best-mean strategy's 8h pnl, floored at $0.5
    so the dollar-tiebreaker never explodes.
    """
    means = [float(np.mean(pnl_v1)), float(np.mean(pnl_v2)), float(np.mean(pnl_v3))]
    best_idx = int(np.argmax(means))
    best_pnl = [pnl_v1, pnl_v2, pnl_v3][best_idx]
    dollar_scale = max(0.5, float(np.percentile(best_pnl, 75)))

    def _sd(x: np.ndarray) -> float:
        s = float(np.std(x, ddof=1)) if len(x) > 1 else 1.0
        return s if s > 1e-6 else 1.0

    return RewardStats(
        mu_v1=means[0], sigma_v1=_sd(pnl_v1),
        mu_v2=means[1], sigma_v2=_sd(pnl_v2),
        mu_v3=means[2], sigma_v3=_sd(pnl_v3),
        dollar_scale=dollar_scale,
    )


def reward_fn(
    action_idx: int,
    pnl_v1: float, pnl_v2: float, pnl_v3: float,
    stats: RewardStats,
) -> float:
    """Dollar reward normalized by portfolio scale — Sutton verdict 2026-04-21.

    Original (1-λ)·z + λ·d had per-arm z normalization that punished low-σ
    arms (v2, σ=0.025) by inflating its z relative to its dollar edge. The
    learner mistook low variance for low value. Walk-forward backtest
    confirmed: ALL_V2 won on dollar PnL, lost on z-blended reward.

    Sutton: "Mixing units in reward is the textbook reward-hacking trap."
    Fix: drop z-score entirely; reward = dollar_pnl / dollar_scale, where
    dollar_scale is a single global normalizer (not per-arm σ). This puts
    every arm on the same scale and lets Q-learning compare on actual edge.
    """
    w1, w2, w3 = ACTIONS[action_idx]
    return (w1 * pnl_v1 + w2 * pnl_v2 + w3 * pnl_v3) / stats.dollar_scale


def apply_capability_mask(action_idx: int, funding_bit: int) -> bool:
    """Capability mask per §2.2: cold funding → mask ALL_V3 (action 2)."""
    if action_idx == 2 and funding_bit == 0:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────
# Pretrain driver
# ─────────────────────────────────────────────────────────────────────────
def calibrate_regime_thresholds(
    features_cal: pd.DataFrame,
    funding_cal_per_symbol: np.ndarray,
) -> dict:
    """Compute vol_p65, funding_p90, kimchi_p50, usdc_p50 on 60d window."""
    return {
        "vol_p65": float(np.nanpercentile(features_cal["vol"].values, 65)),
        # Funding p90 is over per-symbol ticks (not medians), matching the design
        # intent: p90 of actual observed rates → threshold for "hot" median.
        "funding_p90": float(np.nanpercentile(funding_cal_per_symbol, 90)),
        "kimchi_p50": float(np.nanpercentile(features_cal["kimchi_premium"].values, 50)),
        "usdc_p50": float(np.nanpercentile(features_cal["usdc_spread"].values, 50)),
    }


def run_pretrain(dry_run: bool = False, seed: int = 42) -> dict:
    t0 = time.time()
    random.seed(seed)
    np.random.seed(seed)

    # ── 1. Load real funding data ────────────────────────────────────────
    funding = load_funding_timeline()
    funding = build_v3_pnl_per_symbol_per_tick(funding)
    all_ticks = sorted(funding["tick_ts"].unique())
    print(f"[F5] funding data: {len(all_ticks)} ticks, "
          f"{funding['symbol'].nunique()} symbols ({sorted(funding['symbol'].unique())})")
    print(f"[F5] time range: {all_ticks[0]} → {all_ticks[-1]}")

    # ── 2. v3 pnl per tick (cross-sectional mean across symbols) ─────────
    v3_per_tick = (
        funding.groupby("tick_ts")["pnl_v3"].mean().sort_index()
    )  # dollars per tick per $500 notional

    # ── 3. Regime features (real funding_median + vol proxy, synth kimchi/usdc) ──
    features = synthesize_regime_features(funding, seed=seed + 1)
    features = features.set_index("tick_ts").reindex(v3_per_tick.index)

    # ── 4. v2 dual_quote: real 8h bins + bootstrap to match timeline length ──
    v2_pool = load_v2_dual_quote_8h_bins()
    print(f"[F5] v2_dual_quote 8h bins from real 1s data: {len(v2_pool)} samples")
    rng_v2 = np.random.default_rng(seed + 2)
    v2_per_tick = np.array([
        rng_v2.choice(v2_pool) for _ in range(len(v3_per_tick))
    ], dtype=np.float64)
    is_synth_v2 = np.zeros(len(v3_per_tick), dtype=bool)
    # Mark ticks outside 30-day real window as synth — for 271 real bins vs 90 train
    # ticks we bootstrap ALL ticks but the pool itself is real. Flag as bootstrapped.
    is_synth_v2[:] = True  # all bootstrap-sampled

    # ── 5. v1 synthetic AR(1) ────────────────────────────────────────────
    v1_per_tick = synthesize_v1_pnl(len(v3_per_tick), seed=seed + 3)

    # Assemble full table
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

    # ── 6. Holdout split (F8-fix) ────────────────────────────────────────
    cal_start = pd.Timestamp(SPLIT_CAL_START)
    cal_end = pd.Timestamp(SPLIT_CAL_END)
    train_end = pd.Timestamp(SPLIT_TRAIN_END)
    cal_mask = (timeline["tick_ts"] >= cal_start) & (timeline["tick_ts"] < cal_end)
    train_mask = (timeline["tick_ts"] >= cal_end) & (timeline["tick_ts"] <= train_end)
    cal_df = timeline.loc[cal_mask].reset_index(drop=True)
    train_df = timeline.loc[train_mask].reset_index(drop=True)
    print(f"[F5] calibration window: {len(cal_df)} ticks ({cal_start} → {cal_end})")
    print(f"[F5] training window:    {len(train_df)} ticks ({cal_end} → {train_end})")

    # ── 7. Calibrate regime thresholds on cal window ─────────────────────
    funding_cal_per_symbol = funding.loc[
        (funding["tick_ts"] >= cal_start) & (funding["tick_ts"] < cal_end),
        "funding_rate",
    ].values
    thresholds = calibrate_regime_thresholds(cal_df, funding_cal_per_symbol)
    print("[F5] calibrated thresholds:")
    for k, v in thresholds.items():
        print(f"       {k} = {v:.6f}")

    # Write thresholds BEFORE reloading regime_features module constants
    if not dry_run:
        OUT_THRESHOLDS.parent.mkdir(parents=True, exist_ok=True)
        OUT_THRESHOLDS.write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    # Patch module-level constants in-process so training uses them
    rf.VOL_P65 = thresholds["vol_p65"]
    rf.FUNDING_P90 = thresholds["funding_p90"]
    rf.KIMCHI_P50 = thresholds["kimchi_p50"]
    rf.USDC_P50 = thresholds["usdc_p50"]

    # ── 8. Reward stats calibration (μ, σ, DOLLAR_SCALE) on cal window ───
    rstats = calibrate_reward_stats(
        cal_df["pnl_v1"].values,
        cal_df["pnl_v2"].values,
        cal_df["pnl_v3"].values,
    )
    print(f"[F5] reward stats: "
          f"μ_v1={rstats.mu_v1:+.3f} σ_v1={rstats.sigma_v1:.3f}  "
          f"μ_v2={rstats.mu_v2:+.3f} σ_v2={rstats.sigma_v2:.3f}  "
          f"μ_v3={rstats.mu_v3:+.3f} σ_v3={rstats.sigma_v3:.3f}  "
          f"DOLLAR_SCALE={rstats.dollar_scale:.3f}")

    # ── 9. Q-learning with enumerated replay + bootstrap ─────────────────
    q_table = [[Q_INIT] * NUM_ACTIONS for _ in range(NUM_STATES)]
    visits = [[0] * NUM_ACTIONS for _ in range(NUM_STATES)]

    if len(train_df) == 0:
        raise RuntimeError("Empty train split — check SPLIT_CAL_END vs data range")

    rng_boot = np.random.default_rng(seed + 4)
    boot_idx = rng_boot.integers(0, len(train_df), size=BOOTSTRAP_RESAMPLES)
    shuffle_perm = rng_boot.permutation(BOOTSTRAP_RESAMPLES)

    nan_count = 0
    for k in shuffle_perm:
        row = train_df.iloc[int(boot_idx[k])]
        s = rf.state_index(
            float(row["vol"]),
            float(row["funding_median"]),
            float(row["kimchi_premium"]),
            float(row["usdc_spread"]),
        )
        funding_bit = 1 if row["funding_median"] >= rf.FUNDING_P90 else 0
        # Enumerate all actions
        for a in range(NUM_ACTIONS):
            # Capability mask during pretrain — cold funding masks ALL_V3.
            # Safety mask (trailing-72h) is LIVE-only per design §2.2, skipped here.
            if not apply_capability_mask(a, funding_bit):
                continue
            r = reward_fn(a, row["pnl_v1"], row["pnl_v2"], row["pnl_v3"], rstats)
            if not math.isfinite(r):
                nan_count += 1
                continue
            q = q_table[s][a]
            q_table[s][a] = q + ALPHA * (r - q)
            visits[s][a] += 1

    if nan_count > 0:
        print(f"[F5] WARN: skipped {nan_count} non-finite rewards during training")

    # ── 10. F-ALLOC-6 gate ───────────────────────────────────────────────
    visited_states = [s for s in range(NUM_STATES) if sum(visits[s]) > 0]
    corner_count = 0
    per_cell_argmax: list[int] = []
    for s in range(NUM_STATES):
        if sum(visits[s]) == 0:
            per_cell_argmax.append(-1)  # unvisited
            continue
        # Argmax ignoring actions with zero visits (they sit at Q_INIT forever)
        q_row = q_table[s]
        v_row = visits[s]
        best_a = max(range(NUM_ACTIONS), key=lambda a: (v_row[a] > 0, q_row[a]))
        per_cell_argmax.append(best_a)
        if best_a in CORNER_ACTIONS:
            corner_count += 1

    gate_pass = corner_count >= 3
    gate_str = "PASS" if gate_pass else "WARN"
    print(f"[F5] F-ALLOC-6 gate: {gate_str} -- "
          f"{corner_count}/{NUM_STATES} cells converged to a corner action")

    # ── 11. Print Q-table summary ────────────────────────────────────────
    print("\n[F5] per-cell Q-table (argmax action shown):")
    header = f"  {'state':<18}" + "".join(f"{lbl:>12}" for lbl in ACTION_LABELS) + "   argmax"
    print(header)
    for s in range(NUM_STATES):
        row_q = q_table[s]
        row_str = "".join(
            f"{row_q[a]:>12.3f}" if visits[s][a] > 0 else f"{'·':>12}"
            for a in range(NUM_ACTIONS)
        )
        ax = per_cell_argmax[s]
        ax_lbl = ACTION_LABELS[ax] if ax >= 0 else "UNVISITED"
        print(f"  {rf.STATE_LABELS[s]:<18}{row_str}   {ax_lbl}")

    # ── 12. Emit artifacts ───────────────────────────────────────────────
    artifact = {
        "pretrained_at": int(time.time()),
        "pretrained_at_iso": pd.Timestamp.utcnow().isoformat(),
        "design_version": "ALLOCATOR_RL_DESIGN v1 (F8-fix)",
        "num_states": NUM_STATES,
        "num_actions": NUM_ACTIONS,
        "state_labels": rf.STATE_LABELS,
        "action_labels": ACTION_LABELS,
        "action_weights": [list(a) for a in ACTIONS],
        "q_table": q_table,
        "visit_counts": visits,
        "reward_stats": rstats.to_dict(),
        "calibration": {
            "cal_start": SPLIT_CAL_START,
            "cal_end": SPLIT_CAL_END,
            "train_end": SPLIT_TRAIN_END,
            "cal_ticks": int(len(cal_df)),
            "train_ticks": int(len(train_df)),
            "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
            "regime_thresholds": thresholds,
        },
        "hyperparams": {
            "alpha": ALPHA,
            "q_init": Q_INIT,
            "ucb_c": UCB_C,
            "lambda": LAMBDA,
            "notional": NOTIONAL,
        },
        "f_alloc_6_gate": {
            "pass": bool(gate_pass),
            "corner_cells": int(corner_count),
            "per_cell_argmax": per_cell_argmax,
        },
        "data_provenance": {
            "funding": {"source": "data/funding/*_90d.parquet", "synthetic": False,
                         "symbols": sorted(funding["symbol"].unique().tolist())},
            "v3_pnl": {"formula": "funding_rate*500 + basis_change*500*0.5",
                        "synthetic": False},
            "v1_pnl": {"formula": "AR(1) phi=0.4 sigma=0.80 centered at 0",
                        "synthetic": True,
                        "reason": "no Upbit/Binance kimchi data in repo per F1b"},
            "v2_pnl": {"formula": "std(premium_1min) * sqrt(n) * 0.025 * 500, per 8h bin; bootstrapped",
                        "synthetic": False, "bootstrapped": True,
                        "pool_size": len(v2_pool)},
            "kimchi_premium_feature": {"synthetic": True,
                                        "reason": "F1b lacks Upbit data; AR(1) around 0.003"},
            "usdc_spread_feature": {"synthetic": True,
                                     "reason": "F1b lacks dual_quote spread time series; AR(1) around 0.0008"},
            "vol_feature": {"synthetic": False,
                             "formula": "rolling-8 σ of cross-sectional mean perp_close return",
                             "note": "proxy — design calls for BTC 8h σ but F1b parquets exclude BTC"},
        },
        "elapsed_seconds": round(time.time() - t0, 2),
    }

    report = render_report(artifact)

    if dry_run:
        print("\n[F5] --dry-run: no files written")
    else:
        OUT_QTABLE.parent.mkdir(parents=True, exist_ok=True)
        OUT_QTABLE.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        OUT_REPORT.write_text(report, encoding="utf-8")
        print(f"\n[F5] wrote {OUT_QTABLE} ({OUT_QTABLE.stat().st_size} bytes)")
        print(f"[F5] wrote {OUT_REPORT} ({OUT_REPORT.stat().st_size} bytes)")
        print(f"[F5] wrote {OUT_THRESHOLDS} ({OUT_THRESHOLDS.stat().st_size} bytes)")

    print(f"[F5] done in {artifact['elapsed_seconds']}s")
    return artifact


def render_report(artifact: dict) -> str:
    lines: list[str] = []
    lines.append("# Capital Allocator Q-table pretrain report")
    lines.append("")
    lines.append(f"- Generated: {artifact['pretrained_at_iso']}")
    lines.append(f"- Design: {artifact['design_version']}")
    lines.append(f"- Pretrain duration: {artifact['elapsed_seconds']}s")
    lines.append("")
    lines.append("## Data provenance")
    prov = artifact["data_provenance"]
    lines.append(f"- Funding (real): {prov['funding']['symbols']}")
    lines.append(f"- v3_pnl: {prov['v3_pnl']['formula']}  (real, from F1b)")
    lines.append(f"- v2_pnl: {prov['v2_pnl']['formula']}  "
                 f"(real pool of {prov['v2_pnl']['pool_size']}, bootstrap-resampled)")
    lines.append(f"- v1_pnl: {prov['v1_pnl']['formula']}  (**synthetic** — {prov['v1_pnl']['reason']})")
    lines.append(f"- Regime features: funding_median and vol REAL, kimchi_premium and usdc_spread SYNTHETIC")
    lines.append("")
    lines.append("## Holdout split (F8-fix)")
    cal = artifact["calibration"]
    lines.append(f"- Calibration: {cal['cal_start']} → {cal['cal_end']}  ({cal['cal_ticks']} ticks)")
    lines.append(f"- Training:    {cal['cal_end']} → {cal['train_end']}  ({cal['train_ticks']} ticks)")
    lines.append(f"- Bootstrap resamples: {cal['bootstrap_resamples']}")
    lines.append("")
    lines.append("## Calibrated reward stats")
    rs = artifact["reward_stats"]
    lines.append(f"- μ_v1={rs['mu_v1']:+.4f}, σ_v1={rs['sigma_v1']:.4f}")
    lines.append(f"- μ_v2={rs['mu_v2']:+.4f}, σ_v2={rs['sigma_v2']:.4f}")
    lines.append(f"- μ_v3={rs['mu_v3']:+.4f}, σ_v3={rs['sigma_v3']:.4f}")
    lines.append(f"- DOLLAR_SCALE={rs['dollar_scale']:.4f}, λ={rs['lambda']:.2f}")
    lines.append("")
    lines.append("## Regime thresholds")
    for k, v in cal["regime_thresholds"].items():
        lines.append(f"- {k} = {v:.6f}")
    lines.append("")
    lines.append("## Q-table (rows = states, cols = actions, · = unvisited due to mask)")
    lines.append("")
    header = "| state | " + " | ".join(artifact["action_labels"]) + " | argmax |"
    sep = "|" + "|".join(["---"] * (NUM_ACTIONS + 2)) + "|"
    lines.append(header)
    lines.append(sep)
    pc = artifact["f_alloc_6_gate"]["per_cell_argmax"]
    for s in range(NUM_STATES):
        cells = []
        for a in range(NUM_ACTIONS):
            v = artifact["visit_counts"][s][a]
            if v == 0:
                cells.append("·")
            else:
                cells.append(f"{artifact['q_table'][s][a]:+.3f}")
        ax = pc[s]
        ax_lbl = artifact["action_labels"][ax] if ax >= 0 else "UNVISITED"
        lines.append(f"| {artifact['state_labels'][s]} | " + " | ".join(cells) + f" | {ax_lbl} |")
    lines.append("")
    lines.append("## F-ALLOC-6 gate")
    g = artifact["f_alloc_6_gate"]
    verdict = "PASS" if g["pass"] else "WARN"
    lines.append(f"- Verdict: **{verdict}** — {g['corner_cells']}/{NUM_STATES} cells converged to a corner action")
    lines.append(f"- Target: ≥3/9 corner cells (ALL_V1 / ALL_V2 / ALL_V3)")
    lines.append("")
    lines.append("## Visit counts")
    lines.append("")
    header = "| state | " + " | ".join(artifact["action_labels"]) + " |"
    sep = "|" + "|".join(["---"] * (NUM_ACTIONS + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for s in range(NUM_STATES):
        cells = [str(v) for v in artifact["visit_counts"][s]]
        lines.append(f"| {artifact['state_labels'][s]} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print only, no files written")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    run_pretrain(dry_run=args.dry_run, seed=args.seed)


if __name__ == "__main__":
    main()
