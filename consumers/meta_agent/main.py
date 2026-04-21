"""
Meta Agent — Gemini 2.5 Flash powered signal enricher.

Consumer role:
  1. Poll bridge /signals/latest (raw tier, $0.002)
  2. Group by symbol, detect conflicts between producers (kimchi vs dual_quote)
  3. Call Gemini with structured output → confidence_score, notional, regime, justification
  4. Re-publish to bridge as `tier=premium` ($0.01)

This is the "value-add" layer that executor agents actually pay for.

Run:
    python -m consumers.meta_agent.main --interval 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from typing import Any

import requests
from dotenv import load_dotenv

# google-genai is optional at import time so the agent can run in "stub" mode
try:
    from google import genai
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

# Regime GBM (trained offline on v1.3 parquet)
try:
    from ml.regime_gbm import RegimeModel
    GBM_AVAILABLE = True
except Exception:
    GBM_AVAILABLE = False


load_dotenv()

BRIDGE_URL = os.environ.get("ARC_BRIDGE_URL", "http://localhost:3000")
GEMINI_KEY = os.environ.get("GOOGLE_AI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


PROMPT = """You are a cross-venue crypto arbitrage meta-agent.

You receive 1..N raw signals for the same symbol, each from an independent
producer agent. You also receive each producer's realized hit-rate over the
last 200 signals (may be empty on cold start).

Your job is to decide whether the *net* signal is worth paying real money for,
**weighting each producer's claim by its track record**.

Rules:
  - Producers disagreeing on direction → pick the side with higher hit_rate,
    lower overall confidence by 30-40%.
  - If the dominant producer's hit_rate < 0.4 → mark as "kill_switch" by
    returning confidence_score < 0.2 (we filter these out).
  - Premium_rate smaller than typical fees (~0.08%) → lower confidence.
  - Regime labels: "trending" / "mean_revert" / "noise" / "event".
  - notional_usd is suggested size in USD for a $1,000 paper book. Clamp 50–500.
  - Confidence scales DIRECTLY with dominant producer's hit_rate; do not
    hand-wave.

Return STRICT JSON, no prose."""


SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "confidence_score": {"type": "number"},
        "notional_usd": {"type": "number"},
        "expected_profit_usd": {"type": "number"},
        "regime": {"type": "string"},
        "justification": {"type": "string"},
    },
    "required": [
        "action",
        "confidence_score",
        "notional_usd",
        "expected_profit_usd",
        "regime",
        "justification",
    ],
}


def _client():
    if not GENAI_AVAILABLE or not GEMINI_KEY:
        return None
    return genai.Client(api_key=GEMINI_KEY)


def _load_gbm():
    if not GBM_AVAILABLE:
        return None
    try:
        return RegimeModel.load()
    except Exception as e:
        print(f"[meta] gbm load skipped: {e}", file=sys.stderr)
        return None


# In-memory ring of recent premium rates per symbol (for GBM inference)
_PREM_HIST: dict[str, list[float]] = defaultdict(list)


def _update_hist(symbol: str, premium: float) -> list[float]:
    buf = _PREM_HIST[symbol]
    buf.append(premium)
    if len(buf) > 300:
        del buf[:-300]
    return buf


def _stub_enrich(signals: list[dict], reliability: dict[str, dict]) -> dict:
    """Heuristic fallback when Gemini is unavailable — still produces a premium row.
    Now uses producer hit-rate to down-weight low-reliability sources (Karpathy loop).
    """
    prems = [s.get("premium_rate", 0.0) for s in signals]
    avg = sum(prems) / max(len(prems), 1)
    disagree = len({s.get("action") for s in signals}) > 1
    # Pick the producer with the strongest premium; weight its confidence by its hit-rate.
    top = max(signals, key=lambda s: abs(s.get("premium_rate", 0.0)))
    top_producer = str(top.get("producer_id", "unknown"))
    hit_rate = float(reliability.get(top_producer, {}).get("hit_rate", 0.5))
    samples = int(reliability.get(top_producer, {}).get("samples", 0))
    # Bayesian-style shrink to 0.5 when samples are thin
    blended_hr = (hit_rate * samples + 0.5 * 20) / (samples + 20)
    confidence = max(0.0, min(1.0, abs(avg) * 300)) * (0.6 if disagree else 1.0) * blended_hr * 2
    confidence = max(0.0, min(1.0, confidence))
    return {
        "action": top["action"],
        "confidence_score": round(confidence, 3),
        "notional_usd": round(50 + 450 * confidence, 1),
        "expected_profit_usd": round(abs(avg) * (50 + 450 * confidence), 3),
        "regime": "noise" if abs(avg) < 0.0008 else "trending",
        "justification": (
            f"stub: {len(signals)} raw, avg_prem={avg:.5f}, disagree={disagree}, "
            f"top_producer={top_producer}@hr={blended_hr:.2f}(n={samples})"
        ),
    }


def enrich(client, signals: list[dict], reliability: dict[str, dict]) -> dict:
    if client is None:
        return _stub_enrich(signals, reliability)
    # Include producer reliability in the LLM prompt so the model can do the
    # one thing a stub struggles with: weighted conflict arbitration.
    ctx = {
        "signals": signals,
        "producer_reliability_last_200": reliability,
    }
    body = PROMPT + "\n\nINPUT:\n" + json.dumps(ctx, default=str, indent=2)
    try:
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=body,
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA,
                temperature=0.0,  # deterministic demo
            ),
        )
        return json.loads(resp.text)
    except Exception as e:
        print(f"[meta] gemini failed → stub: {e}", file=sys.stderr)
        return _stub_enrich(signals, reliability)


def fetch_raw() -> list[dict]:
    try:
        r = requests.get(f"{BRIDGE_URL}/signals/latest", timeout=3)
        r.raise_for_status()
        return r.json().get("signals", [])
    except Exception as e:
        print(f"[meta] fetch fail: {e}", file=sys.stderr)
        return []


def fetch_reliability() -> dict[str, dict]:
    """Pull per-producer hit-rate so we can price producers by track record.
    Returns {} if the bridge has no outcomes yet (cold start)."""
    try:
        r = requests.get(f"{BRIDGE_URL}/producer/reliability", timeout=3)
        r.raise_for_status()
        return r.json().get("reliability", {})
    except Exception:
        return {}


def publish_premium(original: dict, enriched: dict) -> bool:
    payload: dict[str, Any] = {
        **original,
        **enriched,
        "tier": "premium",
        "producer_id": "meta_agent",
        "strategy": "gemini_meta",
        "timestamp": time.time(),
    }
    try:
        r = requests.post(f"{BRIDGE_URL}/signals/publish", json=payload, timeout=3)
        return r.ok
    except Exception as e:
        print(f"[meta] publish fail: {e}", file=sys.stderr)
        return False


def group_by_symbol(signals: list[dict]) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        buckets[s.get("symbol", "UNK")].append(s)
    return buckets


def tick(client, gbm, seen_keys: set[tuple]) -> int:
    raw = fetch_raw()
    if not raw:
        return 0
    reliability = fetch_reliability()
    published = 0
    for symbol, sigs in group_by_symbol(raw).items():
        last = sigs[-1]
        _update_hist(symbol, float(last.get("premium_rate", 0.0)))
        # Dedupe key — using round(ts, 3) prevents multi-symbol collisions
        # at 1s resolution when producers fire within the same wall-clock second.
        key = (symbol, last.get("action"), round(float(last.get("timestamp", 0)), 3))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        enriched = enrich(client, sigs, reliability)
        if enriched.get("confidence_score", 0) < 0.2:
            continue  # not worth charging $0.01 for
        # GBM override: if we have a trained model, let it speak for regime
        if gbm is not None:
            hist = _PREM_HIST[symbol]
            if len(hist) >= 120:
                try:
                    label, conf = gbm.predict_single(hist[-120:])
                    enriched["regime"] = label
                    # Blend confidences: take the stronger signal
                    enriched["confidence_score"] = round(
                        max(float(enriched["confidence_score"]), conf * 0.8), 3
                    )
                except Exception as e:
                    print(f"[meta] gbm predict fail: {e}", file=sys.stderr)
        if publish_premium(last, enriched):
            published += 1
            print(
                f"[meta] {symbol} {enriched['action']} "
                f"conf={enriched['confidence_score']:.2f} "
                f"size=${enriched['notional_usd']:.0f} "
                f"regime={enriched['regime']}"
            )
    # Trim dedupe set
    if len(seen_keys) > 5000:
        seen_keys.clear()
    return published


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5.0)
    args = ap.parse_args()

    client = _client()
    gbm = _load_gbm()
    mode = "gemini" if client else "stub"
    gbm_mode = "on" if gbm else "off"
    print(f"[meta] starting — bridge={BRIDGE_URL} llm={mode} gbm={gbm_mode} interval={args.interval}s")

    seen: set[tuple] = set()
    total = 0
    try:
        while True:
            total += tick(client, gbm, seen)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\n[meta] stopped. premium signals published: {total}")


if __name__ == "__main__":
    main()
