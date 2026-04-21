"""Unit tests for ml/regime_features.py.

Primary: F-ALLOC-1 forward-looking-features guard. When the caller passes
`reference_ts` plus a dict of feature timestamps, any feature_ts > reference_ts
must raise ValueError. Simulates the "shifted tick" leak the pre-mortem warns
about.
"""
from __future__ import annotations

import pytest

from ml import regime_features as rf


def test_cold_sentinel_on_any_none():
    assert rf.state_index(None, 0.0001, 0.001, 0.0005) == rf.COLD_SENTINEL
    assert rf.state_index(0.02, None, 0.001, 0.0005) == rf.COLD_SENTINEL
    assert rf.state_index(0.02, 0.0001, None, 0.0005) == rf.COLD_SENTINEL
    assert rf.state_index(0.02, 0.0001, 0.001, None) == rf.COLD_SENTINEL


def test_regime_cells_in_range():
    # All 8 combinations produce indices in 0..7
    seen = set()
    for vol in (0.01, 0.05):
        for fund in (0.00001, 0.0002):
            for kimchi in (0.001, 0.01):
                for usdc in (0.0001, 0.002):
                    idx = rf.state_index(vol, fund, kimchi, usdc)
                    assert 0 <= idx <= 7, f"bad idx {idx}"
                    seen.add(idx)
    # All 8 cells reachable
    assert seen == set(range(8))


def test_calm_cold_tight_is_zero():
    # calm / cold funding / tight dislocation → index 0
    idx = rf.state_index(0.01, 0.00001, 0.001, 0.0001)
    assert idx == 0
    assert rf.describe(idx) == "calm/cold/tight"


def test_hot_hot_wide_is_seven():
    idx = rf.state_index(0.05, 0.0002, 0.01, 0.002)
    assert idx == 7
    assert rf.describe(idx) == "hot/hot/wide"


def test_falloc1_forward_looking_feature_raises():
    """F-ALLOC-1: feature window must not extend past tick start."""
    reference_ts = 1_700_000_000  # arbitrary
    # Simulate a leak: kimchi premium was computed using data after tick start.
    feature_ts = {
        "vol": reference_ts - 100,
        "funding_median": reference_ts - 50,
        "kimchi_premium": reference_ts + 10,   # <-- forward-looking!
        "usdc_spread": reference_ts - 5,
    }
    with pytest.raises(ValueError, match="F-ALLOC-1"):
        rf.state_index(
            0.02, 0.0001, 0.005, 0.0005,
            reference_ts=reference_ts, feature_ts=feature_ts,
        )


def test_falloc1_trailing_feature_ok():
    """Same shape as above, but all timestamps are ≤ reference — must pass."""
    reference_ts = 1_700_000_000
    feature_ts = {
        "vol": reference_ts - 100,
        "funding_median": reference_ts - 50,
        "kimchi_premium": reference_ts - 10,
        "usdc_spread": reference_ts - 5,
    }
    idx = rf.state_index(
        0.02, 0.0001, 0.005, 0.0005,
        reference_ts=reference_ts, feature_ts=feature_ts,
    )
    assert 0 <= idx <= 7


def test_describe_handles_sentinel():
    assert rf.describe(rf.COLD_SENTINEL) == "cold-sentinel"


def test_current_thresholds_contains_expected_keys():
    snap = rf.current_thresholds()
    for k in ("vol_p65", "funding_p90", "kimchi_p50", "usdc_p50", "source"):
        assert k in snap
