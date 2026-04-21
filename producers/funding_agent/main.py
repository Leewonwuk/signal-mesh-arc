"""Funding-Rate Signal Producer — wraps v3 pure strategy and emits signals
to the Arc Bridge (Signal Mesh).

Published by F2 for the Allocator RL pipeline (see docs/ALLOCATOR_RL_DESIGN.md).

Two input modes:
  --live              : polls Binance fapi/v1/premiumIndex at the configured
                        cadence, applies v3's should_enter / should_exit pure
                        logic, emits ArbitrageSignal.
  --replay <parquet>  : replays pre-captured funding ticks (F1 may produce
                        this later from fapi/v1/fundingRate). Columns expected:
                        timestamp(ms or s), funding_rate, mark_price, index_price.

Cadence:
  Production:  --cadence-sec 28800   (8h — aligned with funding cycle)
  Demo:        --demo-cadence-sec 30 (judge-visible in a 90s demo)

Signals emitted:
  SignalAction.OPEN_FUNDING_LONG_SPOT_SHORT_PERP — should_enter == True
  SignalAction.CLOSE_FUNDING                    — should_exit returns a reason
  SignalAction.HOLD                             — default (verbose logging only)

Extra payload field:
  strategy_tag = "funding"   (picked up by the allocator / dashboard)
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import requests
from dotenv import load_dotenv

# --- v3 pure-strategy cross-repo import ------------------------------------
# The v3 repo is a sibling hackerton repo. funding_strategy.py is a pure
# function module (no side effects) but uses relative imports against
# src/config_v20.py and src/position_state.py. Adding v3_funding_rate root
# to sys.path lets us `from src.funding_strategy import ...` cleanly, which
# keeps this file as a THIN wrapper (design-doc §8.4).
V3_ROOT = Path(
    os.environ.get(
        "ARC_V3_FUNDING_ROOT",
        r"C:\Users\user\trading\arb\ai_agent_trading_v1.0\v3_funding_rate",
    )
)
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

from src.funding_strategy import should_enter, should_exit  # noqa: E402
from src.config_v20 import FundingArbConfig, load_config  # noqa: E402
from src.position_state import PositionState  # noqa: E402

# --- shared signal schema ---------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.signal import ArbitrageSignal, SignalAction, SignalTier  # noqa: E402

log = logging.getLogger("funding_producer")

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1/premiumIndex"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class FundingProducerConfig:
    symbol: str = "DOGE"                  # e.g. DOGE, TRX, XRP
    spot_symbol: str = "DOGEUSDT"
    futures_symbol: str = "DOGEUSDT"

    # Strategy thresholds (conservative hackathon defaults per F2 brief)
    entry_funding_rate: float = 0.0005    # 0.05% per 8h (≈ 54% APR)
    max_basis_rate: float = 0.003         # 0.3% spot/perp divergence allowed
    exit_funding_rate: float = 0.00005
    stop_loss_usdt: float = -30.0
    max_hold_hours: float = 168.0

    # Producer plumbing
    bridge_url: str = "http://localhost:3000"
    cadence_sec: float = 28800.0          # 8h prod
    request_timeout_sec: float = 5.0

    # Cosmetic fields (fee/capital not used by pure logic here — the allocator
    # owns sizing, we only emit the signal). Kept so the wrapped v3 config
    # can pass its own values through unchanged.
    capital_usdt: float = 500.0
    position_fraction: float = 0.8
    leverage: int = 2
    spot_fee_rate: float = 0.00075
    futures_fee_rate: float = 0.0002

    def to_v3_config(self) -> FundingArbConfig:
        """Build the v3 FundingArbConfig the pure-logic fns expect."""
        return FundingArbConfig(
            symbol=self.symbol,
            spot_symbol=self.spot_symbol,
            futures_symbol=self.futures_symbol,
            capital_usdt=self.capital_usdt,
            position_fraction=self.position_fraction,
            leverage=self.leverage,
            entry_funding_rate=self.entry_funding_rate,
            max_basis_rate=self.max_basis_rate,
            exit_funding_rate=self.exit_funding_rate,
            stop_loss_usdt=self.stop_loss_usdt,
            max_hold_hours=self.max_hold_hours,
            spot_fee_rate=self.spot_fee_rate,
            futures_fee_rate=self.futures_fee_rate,
        )


def load_producer_config(path: Optional[str], overrides: dict) -> FundingProducerConfig:
    """Merge a v3-style yaml with CLI overrides.

    Missing yaml file is fine — brief says "be pragmatic". We fall back to
    the conservative defaults (entry=0.0005, max_basis=0.003).
    """
    cfg = FundingProducerConfig()
    if path:
        try:
            v3cfg = load_config(path)
            cfg.symbol = v3cfg.symbol
            cfg.spot_symbol = v3cfg.spot_symbol
            cfg.futures_symbol = v3cfg.futures_symbol
            cfg.entry_funding_rate = v3cfg.entry_funding_rate
            cfg.max_basis_rate = v3cfg.max_basis_rate
            cfg.exit_funding_rate = v3cfg.exit_funding_rate
            cfg.stop_loss_usdt = v3cfg.stop_loss_usdt
            cfg.max_hold_hours = v3cfg.max_hold_hours
            cfg.capital_usdt = v3cfg.capital_usdt
            cfg.position_fraction = v3cfg.position_fraction
            cfg.leverage = v3cfg.leverage
            cfg.spot_fee_rate = v3cfg.spot_fee_rate
            cfg.futures_fee_rate = v3cfg.futures_fee_rate
            log.info("Loaded v3 config %s (symbol=%s, entry=%.4f%%)",
                     path, cfg.symbol, cfg.entry_funding_rate * 100)
        except (FileNotFoundError, OSError) as e:
            log.warning("Config %s not loadable (%s) — using defaults", path, e)

    # CLI overrides applied AFTER yaml (CLI wins)
    for k, v in overrides.items():
        if v is None:
            continue
        if hasattr(cfg, k):
            setattr(cfg, k, v)

    # Symbol-driven pair naming if not explicit
    if cfg.spot_symbol == "DOGEUSDT" and cfg.symbol != "DOGE":
        cfg.spot_symbol = f"{cfg.symbol}USDT"
        cfg.futures_symbol = f"{cfg.symbol}USDT"
    return cfg


# ---------------------------------------------------------------------------
# Market data sources
# ---------------------------------------------------------------------------
def fetch_live_funding(symbol: str, session: requests.Session, timeout: float) -> dict:
    """Binance USDT-M perp premiumIndex: funding rate + mark + index prices."""
    resp = session.get(BINANCE_FAPI, params={"symbol": symbol}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return {
        "funding_rate": float(data["lastFundingRate"]),
        "mark_price": float(data["markPrice"]),
        "index_price": float(data["indexPrice"]),
        "next_funding_time": int(data.get("nextFundingTime", 0)),
    }


def replay_ticks(parquet_path: str) -> Iterator[dict]:
    """Yield funding-rate snapshots from a pre-captured parquet.

    Expected columns: timestamp, funding_rate, mark_price, index_price.
    If index_price is missing we reuse mark_price (basis=0 that tick).
    """
    import pandas as pd  # pip install pandas pyarrow
    df = pd.read_parquet(parquet_path)
    for _, row in df.iterrows():
        mark = float(row.get("mark_price", row.get("mark", 0.0)))
        index = float(row.get("index_price", row.get("index", mark)))
        yield {
            "funding_rate": float(row["funding_rate"]),
            "mark_price": mark,
            "index_price": index,
            "next_funding_time": int(row.get("timestamp", 0)),
        }


# ---------------------------------------------------------------------------
# Signal publishing
# ---------------------------------------------------------------------------
def publish_signal(signal: ArbitrageSignal, bridge_url: str,
                   session: requests.Session, extra: Optional[dict] = None) -> bool:
    payload = signal.to_dict()
    if extra:
        payload.update(extra)
    try:
        resp = session.post(
            f"{bridge_url}/signals/publish",
            json=payload,
            timeout=2.0,
        )
        if resp.status_code == 200:
            return True
        log.warning("Bridge replied %s: %s", resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        log.warning("Bridge POST failed: %s", e)
    return False


def build_signal(
    cfg: FundingProducerConfig,
    action: SignalAction,
    funding_rate: float,
    spot: float,
    futures: float,
    reason: str,
) -> ArbitrageSignal:
    return ArbitrageSignal(
        timestamp=time.time(),
        producer_id="funding_agent",
        strategy="funding_rate_basis",
        symbol=cfg.symbol,
        action=action,
        premium_rate=funding_rate,
        bid_price_a=spot,       # spot side
        ask_price_a=spot,
        bid_price_b=futures,    # perp side
        ask_price_b=futures,
        reason=reason,
        tier=SignalTier.RAW,
        expected_profit_usd=funding_rate * cfg.capital_usdt * cfg.position_fraction,
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run_loop(
    cfg: FundingProducerConfig,
    mode: str,
    replay_path: Optional[str],
    max_duration_sec: Optional[float],
    verbose: bool,
) -> None:
    """Pump funding-rate snapshots through v3's pure logic and publish."""
    session = requests.Session()
    v3_cfg = cfg.to_v3_config()
    position: Optional[PositionState] = None

    if mode == "replay":
        if not replay_path:
            raise SystemExit("--replay requires a parquet path")
        source: Iterator[dict] = replay_ticks(replay_path)
    else:
        def live_gen() -> Iterator[dict]:
            while True:
                try:
                    yield fetch_live_funding(cfg.futures_symbol, session,
                                             cfg.request_timeout_sec)
                except requests.RequestException as e:
                    log.warning("premiumIndex fetch failed: %s", e)
                    yield {}  # skip tick, keep cadence
        source = live_gen()

    start = time.monotonic()
    stopping = {"flag": False}

    def _shutdown(signum, frame):  # pragma: no cover
        stopping["flag"] = True
        log.info("Signal %s received — shutting down cleanly", signum)

    try:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    except (ValueError, AttributeError):
        pass  # Not on main thread / Windows edge

    published = 0
    tick_n = 0
    for snap in source:
        if stopping["flag"]:
            break
        if max_duration_sec is not None and time.monotonic() - start >= max_duration_sec:
            log.info("Max duration %ss reached — exiting", max_duration_sec)
            break
        if not snap:
            time.sleep(min(cfg.cadence_sec, 2.0))
            continue

        tick_n += 1
        fr = snap["funding_rate"]
        mark = snap["mark_price"]
        idx = snap["index_price"]
        # spot proxy = index price (underlying average); futures = mark price.
        spot, futures = idx, mark

        if position is None:
            ok, reason = should_enter(fr, spot, futures, v3_cfg)
            if ok:
                sig = build_signal(
                    cfg, SignalAction.OPEN_FUNDING_LONG_SPOT_SHORT_PERP,
                    fr, spot, futures, reason,
                )
                if publish_signal(sig, cfg.bridge_url, session,
                                  extra={"strategy_tag": "funding"}):
                    published += 1
                    log.info("[tick %d] OPEN fr=%.4f%% basis=%.4f%% %s",
                             tick_n, fr * 100,
                             ((futures - spot) / spot * 100) if spot else 0.0,
                             reason)
                    # Track a lightweight virtual position so should_exit gets
                    # sensible inputs. Real capital sizing belongs to the
                    # allocator/executor — we just need a PositionState so
                    # net_pnl() works when funding turns.
                    position = PositionState(
                        symbol=cfg.symbol,
                        spot_qty=cfg.capital_usdt * cfg.position_fraction / max(spot, 1e-9),
                        spot_entry_price=spot,
                        spot_entry_cost=cfg.capital_usdt * cfg.position_fraction * cfg.spot_fee_rate,
                        futures_qty=cfg.capital_usdt * cfg.position_fraction / max(futures, 1e-9),
                        futures_entry_price=futures,
                        futures_entry_cost=cfg.capital_usdt * cfg.position_fraction * cfg.futures_fee_rate,
                        entry_funding_rate=fr,
                        entry_basis=futures - spot,
                    )
            else:
                if verbose:
                    log.info("[tick %d] HOLD fr=%.4f%% %s",
                             tick_n, fr * 100, reason)
        else:
            exit_reason, msg = should_exit(position, fr, spot, futures, None, v3_cfg)
            if exit_reason is not None:
                sig = build_signal(
                    cfg, SignalAction.CLOSE_FUNDING,
                    fr, spot, futures, f"{exit_reason.value}: {msg}",
                )
                if publish_signal(sig, cfg.bridge_url, session,
                                  extra={"strategy_tag": "funding",
                                         "exit_reason": exit_reason.name}):
                    published += 1
                    log.info("[tick %d] CLOSE %s | %s",
                             tick_n, exit_reason.name, msg)
                position = None
            elif verbose:
                log.info("[tick %d] HOLD (in position) fr=%.4f%% %s",
                         tick_n, fr * 100, msg)

        if mode == "replay":
            # Replay cadence: fire ticks as fast as cfg allows. The brief
            # implies 8h-between-ticks; for replay we still honour cadence
            # so the allocator sees a realistic cycle if configured demo-fast.
            time.sleep(min(cfg.cadence_sec, 0.05))
        else:
            time.sleep(cfg.cadence_sec)

    log.info("Producer done. Ticks=%d Published=%d", tick_n, published)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    p = argparse.ArgumentParser(
        description="Funding-rate signal producer (Allocator RL / F2)"
    )
    p.add_argument("--symbol", default=None,
                   help="Coin symbol (DOGE, TRX, XRP, ...). Overrides config.")
    p.add_argument("--config", default=None,
                   help="Path to v3 yaml config (configs/v20_*.yaml). Optional.")
    p.add_argument("--bridge-url",
                   default=os.getenv("ARC_BRIDGE_URL", "http://localhost:3000"))
    p.add_argument("--entry-funding-rate", type=float, default=None,
                   help="Override entry threshold (default 0.0005 = 0.05%% / 8h)")
    p.add_argument("--max-basis-rate", type=float, default=None,
                   help="Override max basis divergence (default 0.003 = 0.3%%)")
    # Cadence — prod vs demo
    p.add_argument("--cadence-sec", type=float, default=28800.0,
                   help="Production poll cadence in seconds (default 28800 = 8h)")
    p.add_argument("--demo-cadence-sec", type=float, default=None,
                   help="Demo override — use this instead of --cadence-sec "
                        "(e.g. 30 for a 90s judge demo)")
    # Mode
    mode_grp = p.add_mutually_exclusive_group()
    mode_grp.add_argument("--live", action="store_true",
                          help="Poll Binance fapi/v1/premiumIndex (default)")
    mode_grp.add_argument("--replay", default=None,
                          help="Path to parquet with funding_rate/mark/index columns")
    p.add_argument("--speed", type=float, default=1.0,
                   help="Replay speed multiplier (unused in live)")
    p.add_argument("--max-duration-sec", type=float, default=None,
                   help="Exit cleanly after this many seconds (smoke tests)")
    p.add_argument("--verbose", action="store_true",
                   help="Log HOLD ticks too")
    args = p.parse_args()

    overrides = {
        "symbol": args.symbol,
        "bridge_url": args.bridge_url,
        "entry_funding_rate": args.entry_funding_rate,
        "max_basis_rate": args.max_basis_rate,
        "cadence_sec": args.demo_cadence_sec if args.demo_cadence_sec else args.cadence_sec,
    }

    cfg = load_producer_config(args.config, overrides)

    # Keep conservative F2 defaults unless user explicitly changed them
    if args.entry_funding_rate is None and args.config is None:
        cfg.entry_funding_rate = 0.0005
    if args.max_basis_rate is None and args.config is None:
        cfg.max_basis_rate = 0.003

    mode = "replay" if args.replay else "live"
    log.info(
        "funding_agent start | symbol=%s mode=%s cadence=%ss entry=%.4f%% max_basis=%.4f%%",
        cfg.symbol, mode, cfg.cadence_sec,
        cfg.entry_funding_rate * 100, cfg.max_basis_rate * 100,
    )

    run_loop(
        cfg=cfg,
        mode=mode,
        replay_path=args.replay,
        max_duration_sec=args.max_duration_sec,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
