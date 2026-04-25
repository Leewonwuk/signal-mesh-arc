"""Demo regime injector — rotates the allocator through a realistic subset
of populated regimes so the Policy Heatmap and AllocatorCard show non-trivial
behaviour during the 2-min screencast.

WHY THIS EXISTS
---------------
The pretrained Q-table (consumers/capital_allocator/allocator_q.json) has
strong learned policy in states s0, s2, s3, s4, s5, s7 (check
`pretrain_report.md`). But a 2-min demo can't wait for the live Binance
vol/funding feeds to actually flip across 8 regimes — and kimchi/usdc proxies
are AR(1) synthetic so they rarely straddle the thresholds in 2 min either.

We write `ml/regime_override.json` every INTERVAL seconds with the four
regime features set to values that deterministically place the allocator
into the next state in ROTATION. The allocator's FeatureSource reads this
file fresh each tick (see consumers/capital_allocator/main.py `_file_override`).

CALIBRATION NOTES
-----------------
Thresholds from ml/regime_thresholds.json (calibrated on pretrain window):
  vol_p65      = 0.0238  → calm: 0.015, hot: 0.050
  funding_p90  = 8.05e-05 → cold: 2.0e-05, hot: 1.5e-04
  kimchi_p50   = 0.00160 → tight: 0.0010, wide: 0.0040
  usdc_p50     = 0.00079 → tight: 0.00030, wide: 0.00200

Each recipe value sits safely below/above its threshold with ≥30% margin so
rounding and minor threshold drift don't flip a bit on us mid-demo.

HONESTY NOTE
------------
This is a *demo injector* — it stands in for what would otherwise be slow
real-time regime rotation. In the prod 8h cadence, the allocator reads live
Binance REST / bridge signals with no override. The SUBMISSION.md notes this
under §11 (demo-only aids). Code labels its output clearly with the
`stub_demo_injection: true` flag in the JSON.

Usage
-----
    python -m demo.regime_injector --interval 12 --rotation s4,s2,s0,s3,s5,s7

Default rotation picks the 6 states with the sharpest policy gradient so
viewers see ALL_V1 → ALL_V2 → ALL_V3 actions all appear within ~60s.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal as signal_mod
import sys
import time
from pathlib import Path

# ── Regime recipe table ───────────────────────────────────────────────────
# Each recipe produces a specific state_index when fed to regime_features
# thresholds. See regime_features.STATE_LABELS for the mapping.
RECIPES: dict[str, dict] = {
    "s0": {  # calm / cold / tight  → pretrained Q argmax = ALL_V3
        "vol": 0.015, "funding_median": 2.0e-05,
        "kimchi_premium": 0.0010, "usdc_spread": 0.00030,
        "label": "calm/cold/tight",
    },
    "s1": {  # calm / cold / wide  → Q argmax = ALL_V3
        "vol": 0.015, "funding_median": 2.0e-05,
        "kimchi_premium": 0.0040, "usdc_spread": 0.00200,
        "label": "calm/cold/wide",
    },
    "s2": {  # calm / hot / tight  → Q argmax = ALL_V2
        "vol": 0.015, "funding_median": 1.5e-04,
        "kimchi_premium": 0.0010, "usdc_spread": 0.00030,
        "label": "calm/hot/tight",
    },
    "s3": {  # calm / hot / wide   → Q argmax = ALL_V2
        "vol": 0.015, "funding_median": 1.5e-04,
        "kimchi_premium": 0.0040, "usdc_spread": 0.00200,
        "label": "calm/hot/wide",
    },
    "s4": {  # hot  / cold / tight → Q argmax = ALL_V1 (strongest: 3.221)
        "vol": 0.050, "funding_median": 2.0e-05,
        "kimchi_premium": 0.0010, "usdc_spread": 0.00030,
        "label": "hot/cold/tight",
    },
    "s5": {  # hot  / cold / wide  → Q argmax = ALL_V1
        "vol": 0.050, "funding_median": 2.0e-05,
        "kimchi_premium": 0.0040, "usdc_spread": 0.00200,
        "label": "hot/cold/wide",
    },
    "s6": {  # hot / hot / tight   → Q tied (untrained cell)
        "vol": 0.050, "funding_median": 1.5e-04,
        "kimchi_premium": 0.0010, "usdc_spread": 0.00030,
        "label": "hot/hot/tight",
    },
    "s7": {  # hot / hot / wide    → Q argmax = ALL_V2
        "vol": 0.050, "funding_median": 1.5e-04,
        "kimchi_premium": 0.0040, "usdc_spread": 0.00200,
        "label": "hot/hot/wide",
    },
}

# Default rotation — picks the pretrained-populated states with the
# sharpest policy gradient so viewers see ALL_V1, ALL_V2, ALL_V3 all trigger.
DEFAULT_ROTATION = ["s4", "s2", "s0", "s5", "s3", "s7"]


def default_override_path() -> Path:
    return Path(__file__).resolve().parent.parent / "ml" / "regime_override.json"


def write_recipe(path: Path, key: str) -> dict:
    recipe = RECIPES[key]
    payload = {
        "vol": recipe["vol"],
        "funding_median": recipe["funding_median"],
        "kimchi_premium": recipe["kimchi_premium"],
        "usdc_spread": recipe["usdc_spread"],
        "state_hint": key,
        "state_label": recipe["label"],
        "stub_demo_injection": True,
        "injected_at": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def clear_override(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Demo regime injector for Q-learning allocator.")
    ap.add_argument(
        "--rotation", default=",".join(DEFAULT_ROTATION),
        help=f"comma-separated regime keys from {sorted(RECIPES)}. "
             f"Default rotates through 6 populated cells so ALL_V1/V2/V3 all fire.",
    )
    ap.add_argument(
        "--interval", type=int, default=12,
        help="seconds between regime flips. Default 12s ≈ 1 flip / 40% of a 30s allocator tick.",
    )
    ap.add_argument(
        "--max-flips", type=int, default=0,
        help="stop after N flips (0 = loop until killed).",
    )
    ap.add_argument(
        "--override-path", default=str(default_override_path()),
        help="JSON file to write. Allocator reads ARC_REGIME_OVERRIDE or this default.",
    )
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s regime_injector %(message)s",
    )
    log = logging.getLogger("regime_injector")

    rotation = [k.strip() for k in args.rotation.split(",") if k.strip()]
    invalid = [k for k in rotation if k not in RECIPES]
    if invalid:
        log.error("invalid rotation keys: %s (valid: %s)", invalid, sorted(RECIPES))
        return 2
    if not rotation:
        log.error("rotation is empty")
        return 2

    path = Path(args.override_path)
    log.info("writing override to %s", path)
    log.info("rotation: %s  interval=%ds", " → ".join(rotation), args.interval)

    stopping = {"flag": False}

    def _shutdown(_signum, _frame):
        stopping["flag"] = True
        log.info("shutdown requested")

    try:
        signal_mod.signal(signal_mod.SIGINT, _shutdown)
        signal_mod.signal(signal_mod.SIGTERM, _shutdown)
    except (ValueError, AttributeError):
        pass

    flips = 0
    idx = 0
    try:
        while not stopping["flag"]:
            key = rotation[idx % len(rotation)]
            payload = write_recipe(path, key)
            log.info(
                "flip %d → %s (%s) vol=%.3f fund=%.5f kimchi=%.4f usdc=%.5f",
                flips + 1, key, payload["state_label"],
                payload["vol"], payload["funding_median"],
                payload["kimchi_premium"], payload["usdc_spread"],
            )
            flips += 1
            if args.max_flips and flips >= args.max_flips:
                log.info("max-flips=%d reached", args.max_flips)
                break
            idx += 1
            slept = 0.0
            while slept < args.interval and not stopping["flag"]:
                time.sleep(min(0.5, args.interval - slept))
                slept += 0.5
    finally:
        # Leave the last recipe in place so a post-demo inspector can still
        # see a populated state. Comment this out if you want shutdown to
        # force-cold the allocator.
        log.info("exit. flips=%d last=%s (left override in place)", flips, rotation[(idx - 1) % len(rotation)])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
