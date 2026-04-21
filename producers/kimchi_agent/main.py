"""
Kimchi Premium Producer — Upbit(KRW) ↔ Binance(USDT) arbitrage signal agent.

The v1.1 live system subscribes to Upbit + Binance WS + a FX feed for KRW/USDT.
For the hackathon demo we don't have those live feeds (and faking live creds
is fragile on a recording), so this module runs in **replay / synthetic** mode:

  - Replay: if `KIMCHI_REPLAY_CSV` points at a CSV with columns
    `timestamp,upbit_bid,upbit_ask,binance_bid,binance_ask,fx_krw_per_usdt`,
    we stream it tick-by-tick.
  - Synthetic: otherwise we generate a mean-reverting kimchi premium path
    around +1.2% with occasional spikes, so the demo still exercises the
    real v1.1 `calc_edge` + `SignalEngine.decide` code paths. This is
    explicitly labeled in the signal `reason` so judges aren't misled.

The strategic point for the hackathon is **two independent producers with
different opinions on the same universe**. Kimchi's USDT-direction signals
will frequently *disagree* with dual-quote's USDT-direction signals, and
that's the cross-producer conflict the Gemini meta-agent is designed to
arbitrate.
"""
from __future__ import annotations

import argparse
import csv
import logging
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv

from .models import OrderBookTop, SpreadInput, utc_now_iso
from .signal_engine import SignalEngine
from .spread_calc import calc_edge

sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.signal import ArbitrageSignal, SignalAction, SignalTier  # noqa: E402


log = logging.getLogger("kimchi_producer")


@dataclass
class KimchiConfig:
    symbol: str = "BTC"
    bridge_url: str = "http://localhost:3000"
    # v1.1 live defaults
    entry_threshold_rate: float = 0.006   # 0.6% post-cost edge
    exit_threshold_rate: float = 0.002
    cooldown_sec: int = 3
    fee_upbit_rate: float = 0.0005
    fee_binance_rate: float = 0.0005
    slippage_upbit_rate: float = 0.0005
    slippage_binance_rate: float = 0.0005
    trade_size_base: float = 0.01          # 0.01 BTC
    # Replay / synthetic
    replay_csv: str | None = None
    tick_interval: float = 1.0
    max_ticks: int = 600
    seed: int = 42


_V1_TO_SIGNAL = {
    "OPEN_UPBIT_SHORT_BINANCE_LONG": SignalAction.OPEN_UPBIT_SHORT_BINANCE_LONG,
    "OPEN_UPBIT_LONG_BINANCE_SHORT": SignalAction.OPEN_UPBIT_LONG_BINANCE_SHORT,
    "CLOSE": SignalAction.CLOSE,
    "HOLD": SignalAction.HOLD,
}


def _synthetic_tick_gen(seed: int):
    """Generate a mean-reverting KRW/USDT premium path around +1.2% with spikes.

    Yields (upbit_bid_krw, upbit_ask_krw, binance_bid_usdt, binance_ask_usdt, fx_krw_per_usdt).
    """
    rng = random.Random(seed)
    t = 0
    binance_mid = 95000.0   # USDT price for BTC
    fx = 1350.0             # KRW per USDT
    premium = 0.012         # kimchi starting premium, 1.2%
    while True:
        # random walk on binance
        binance_mid *= math.exp(rng.gauss(0, 0.0003))
        # mean-reverting premium around 1.2%
        premium += (0.012 - premium) * 0.05 + rng.gauss(0, 0.0008)
        # occasional spike (~1%)
        if rng.random() < 0.02:
            premium += rng.choice([-0.01, 0.01])

        binance_bid = binance_mid * (1 - 0.0002)
        binance_ask = binance_mid * (1 + 0.0002)
        upbit_mid_krw = binance_mid * fx * (1 + premium)
        upbit_bid = upbit_mid_krw * (1 - 0.0003)
        upbit_ask = upbit_mid_krw * (1 + 0.0003)
        yield upbit_bid, upbit_ask, binance_bid, binance_ask, fx
        t += 1


def _csv_tick_gen(path: Path):
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield (
                float(row["upbit_bid"]),
                float(row["upbit_ask"]),
                float(row["binance_bid"]),
                float(row["binance_ask"]),
                float(row["fx_krw_per_usdt"]),
            )


def _build_signal(
    cfg: KimchiConfig, decision, edge, binance_bid: float, binance_ask: float,
    upbit_bid_krw: float, upbit_ask_krw: float, source: str,
) -> ArbitrageSignal:
    # Best edge rate = "premium rate" in the unified schema
    edge_rate = max(edge.upbit_to_binance_edge_rate, edge.binance_to_upbit_edge_rate)
    return ArbitrageSignal(
        timestamp=time.time(),
        producer_id="kimchi_agent",
        strategy="kimchi_premium_krw_usdt",
        symbol=cfg.symbol,
        action=_V1_TO_SIGNAL.get(decision.action, SignalAction.HOLD),
        premium_rate=edge_rate,
        bid_price_a=upbit_bid_krw,
        ask_price_a=upbit_ask_krw,
        bid_price_b=binance_bid,
        ask_price_b=binance_ask,
        reason=f"{decision.reason} ({source})",
        tier=SignalTier.RAW,
        expected_profit_usd=round(edge_rate * cfg.trade_size_base * binance_ask, 4),
    )


def publish_signal(sig: ArbitrageSignal, url: str, session: requests.Session) -> bool:
    try:
        r = session.post(f"{url}/signals/publish", json=sig.to_dict(), timeout=2.0)
        return r.ok
    except requests.RequestException as e:
        log.warning("bridge POST failed: %s", e)
        return False


def run(cfg: KimchiConfig) -> None:
    engine = SignalEngine(
        entry_threshold_rate=cfg.entry_threshold_rate,
        exit_threshold_rate=cfg.exit_threshold_rate,
        cooldown_sec=cfg.cooldown_sec,
    )
    session = requests.Session()

    if cfg.replay_csv:
        source = "csv"
        ticks = _csv_tick_gen(Path(cfg.replay_csv))
    else:
        source = "synthetic"
        ticks = _synthetic_tick_gen(cfg.seed)

    has_position = False
    position_open_at: float | None = None
    published = 0

    for i, (ub, ua, bb, ba, fx) in enumerate(ticks):
        if i >= cfg.max_ticks:
            break
        snap = SpreadInput(
            upbit_krw=OrderBookTop("upbit", f"{cfg.symbol}-KRW", ub, ua, utc_now_iso()),
            binance_usdt=OrderBookTop("binance", f"{cfg.symbol}USDT", bb, ba, utc_now_iso()),
            fx_krw_per_usdt=fx,
            fee_upbit_rate=cfg.fee_upbit_rate,
            fee_binance_rate=cfg.fee_binance_rate,
            slippage_upbit_rate=cfg.slippage_upbit_rate,
            slippage_binance_rate=cfg.slippage_binance_rate,
        )
        try:
            edge = calc_edge(snap, cfg.symbol, cfg.trade_size_base)
        except ValueError:
            continue

        decision = engine.decide(edge, has_position, position_open_at)

        if decision.action.startswith("OPEN"):
            has_position = True
            position_open_at = time.time()
        elif decision.action == "CLOSE":
            has_position = False
            position_open_at = None

        if decision.action != "HOLD":
            sig = _build_signal(cfg, decision, edge, bb, ba, ub, ua, source=source)
            if publish_signal(sig, cfg.bridge_url, session):
                published += 1
                log.info(
                    "[%s] %s edge=%.4f%% (source=%s, pub=%d)",
                    cfg.symbol, decision.action, edge.upbit_to_binance_edge_rate * 100,
                    source, published,
                )

        time.sleep(cfg.tick_interval)

    log.info("replay done. signals published: %d", published)


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC")
    ap.add_argument("--bridge-url", default=os.getenv("ARC_BRIDGE_URL", "http://localhost:3000"))
    ap.add_argument("--replay-csv", default=os.getenv("KIMCHI_REPLAY_CSV"))
    ap.add_argument("--tick-interval", type=float, default=1.0)
    ap.add_argument("--max-ticks", type=int, default=600)
    ap.add_argument("--threshold", type=float, default=0.006,
                    help="entry threshold rate (0.006 = 0.6%% post-cost edge)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    cfg = KimchiConfig(
        symbol=args.symbol,
        bridge_url=args.bridge_url,
        replay_csv=args.replay_csv,
        tick_interval=args.tick_interval,
        max_ticks=args.max_ticks,
        entry_threshold_rate=args.threshold,
        seed=args.seed,
    )
    run(cfg)


if __name__ == "__main__":
    main()
