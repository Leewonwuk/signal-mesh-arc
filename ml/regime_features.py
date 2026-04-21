"""Regime feature encoder — single source of truth for allocator state.

Per ALLOCATOR_RL_DESIGN.md §1:
  2 (vol) × 2 (funding) × 2 (dislocation) = 8 regime cells + 1 "cold" sentinel = 9.

`state_index(vol, funding_median, kimchi_premium, usdc_spread)` maps the four
features to an int in 0..8. Any None input → cold sentinel (index 8), which
the allocator routes to the DIVERSIFY action.

Threshold calibration
---------------------
Thresholds live as module constants but are refreshed at import-time from
`ml/regime_thresholds.json` if that file exists. The pretrain script
(`scripts/pretrain_allocator_q.py`) writes that file after computing
percentiles on its 60-day calibration window — so live and training use the
exact same boundaries.

Defaults (fall-back when no calibration file exists) are the design-doc
numbers, anchored to F1b output statistics:
  vol p65 = 0.035        (8h realized σ across top-5 perps)
  funding p90 = 0.00010  (F1b showed p90 ≈ 1bp / 8h — net-negative regime,
                          so ~10% of ticks qualify as "hot funding"; v3's
                          corner action is hard-earned)
  kimchi p50 = 0.005     (0.5% cross-border dislocation)
  usdc_spread p50 = 0.0008  (8bp intra-venue dislocation)

F-ALLOC-1 guarantee: all features are trailing windows, never forward-looking.
The `reference_ts` arg (when provided) asserts every feature timestamp ≤
reference. Unit test in ml/tests/test_regime_features.py fires on shifted tick.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ── Module-level defaults (fall-back) ─────────────────────────────────────
VOL_P65_DEFAULT = 0.035
FUNDING_P90_DEFAULT = 0.00010
KIMCHI_P50_DEFAULT = 0.005
USDC_P50_DEFAULT = 0.0008

# Mutable — overridden by regime_thresholds.json if present.
VOL_P65 = VOL_P65_DEFAULT
FUNDING_P90 = FUNDING_P90_DEFAULT
KIMCHI_P50 = KIMCHI_P50_DEFAULT
USDC_P50 = USDC_P50_DEFAULT

NUM_STATES = 9
COLD_SENTINEL = 8

# State labels for dashboard. Ordering matches state_index() math below:
#   idx = vol_bit * 4 + funding_bit * 2 + dislocation_bit
#   vol_bit: 0 = calm, 1 = hot
#   funding_bit: 0 = cold, 1 = hot
#   dislocation_bit: 0 = tight, 1 = wide
STATE_LABELS: list[str] = [
    "calm/cold/tight",   # 0
    "calm/cold/wide",    # 1
    "calm/hot/tight",    # 2
    "calm/hot/wide",     # 3
    "hot/cold/tight",    # 4
    "hot/cold/wide",     # 5
    "hot/hot/tight",     # 6
    "hot/hot/wide",      # 7
    "cold-sentinel",     # 8
]

# ── Threshold file location ───────────────────────────────────────────────
_THRESHOLDS_PATH = Path(__file__).resolve().parent / "regime_thresholds.json"


def _load_thresholds_from_disk() -> None:
    """Overwrite module-level threshold constants from regime_thresholds.json.

    Called at import and after an explicit pretrain writes a new JSON.
    """
    global VOL_P65, FUNDING_P90, KIMCHI_P50, USDC_P50
    if not _THRESHOLDS_PATH.exists():
        return
    try:
        d = json.loads(_THRESHOLDS_PATH.read_text(encoding="utf-8"))
        VOL_P65 = float(d.get("vol_p65", VOL_P65_DEFAULT))
        FUNDING_P90 = float(d.get("funding_p90", FUNDING_P90_DEFAULT))
        KIMCHI_P50 = float(d.get("kimchi_p50", KIMCHI_P50_DEFAULT))
        USDC_P50 = float(d.get("usdc_p50", USDC_P50_DEFAULT))
    except Exception:
        # Corrupt file — keep defaults. (Silent so we don't break imports.)
        pass


_load_thresholds_from_disk()


def reload_thresholds() -> dict:
    """Re-read regime_thresholds.json (call after pretrain rewrites it)."""
    _load_thresholds_from_disk()
    return {
        "vol_p65": VOL_P65,
        "funding_p90": FUNDING_P90,
        "kimchi_p50": KIMCHI_P50,
        "usdc_p50": USDC_P50,
    }


def state_index(
    vol: Optional[float],
    funding_median: Optional[float],
    kimchi_premium: Optional[float],
    usdc_spread: Optional[float],
    reference_ts: Optional[int] = None,
    feature_ts: Optional[dict] = None,
) -> int:
    """Map four regime features to an integer state index in 0..8.

    Parameters
    ----------
    vol
        Trailing 8h realized σ of BTC (or median across top-5 perps). None → cold.
    funding_median
        Median of top-N perps funding rate at the most recent 8h tick
        (dimensionless fraction per 8h). None → cold.
    kimchi_premium
        KRW/USDT premium at tick start (dimensionless fraction). None → cold.
    usdc_spread
        USDT-USDC intra-venue spread (dimensionless fraction). None → cold.
    reference_ts
        Optional tick start (seconds since epoch). When provided alongside
        `feature_ts`, asserts every feature timestamp ≤ reference_ts — this is
        the F-ALLOC-1 forward-looking-features guard.
    feature_ts
        Optional dict of feature-name → timestamp used to compute that feature.
        Only consulted when `reference_ts` is set.

    Returns
    -------
    int
        0..7 — one of the 8 regime cells, or 8 if any input is None.
    """
    # F-ALLOC-1 guard
    if reference_ts is not None and feature_ts:
        for name, ts in feature_ts.items():
            if ts is None:
                continue
            if ts > reference_ts:
                raise ValueError(
                    f"F-ALLOC-1 violation: feature '{name}' ts={ts} > "
                    f"reference_ts={reference_ts} (forward-looking window)"
                )

    if (
        vol is None
        or funding_median is None
        or kimchi_premium is None
        or usdc_spread is None
    ):
        return COLD_SENTINEL

    vol_bit = 1 if vol >= VOL_P65 else 0
    funding_bit = 1 if funding_median >= FUNDING_P90 else 0
    disloc_bit = 1 if (kimchi_premium >= KIMCHI_P50 or usdc_spread >= USDC_P50) else 0

    return vol_bit * 4 + funding_bit * 2 + disloc_bit


def describe(idx: int) -> str:
    """Human label for state idx (for dashboard/logging)."""
    if 0 <= idx < NUM_STATES:
        return STATE_LABELS[idx]
    return f"invalid({idx})"


def current_thresholds() -> dict:
    """Snapshot of active thresholds (for /allocation payloads / debugging)."""
    return {
        "vol_p65": VOL_P65,
        "funding_p90": FUNDING_P90,
        "kimchi_p50": KIMCHI_P50,
        "usdc_p50": USDC_P50,
        "source": "regime_thresholds.json" if _THRESHOLDS_PATH.exists() else "defaults",
    }
