"""Dual-Quote Signal Producer — replays 1s parquet data from v1.3 backtest dataset,
runs `decide_v2()`, and POSTs signals to the Arc Bridge.

Replay source is NOT synthetic: the parquet files are captured from the
submitter's live v1.3 production arbitrage bot running on EC2 (9 coins,
pool ≈ $1977 USDT, threshold 0.17%, stop-loss 0.25%). Default capture
date is 20260419. See `producers/README.md` for the full provenance note.

Parquet replay chosen over live Binance WS for demo determinism.
For "live" mode, swap `ParquetReplayFeed` with `PriceFeed` from v1.3.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd  # pip install pandas pyarrow
import requests
from dotenv import load_dotenv

# Local
from .allocator import ActionV2, decide_v2

# Shared schema
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.signal import ArbitrageSignal, SignalAction, SignalTier  # noqa: E402

log = logging.getLogger("dual_quote_producer")


_REPO_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "v1_3_replay"
_LEGACY_PRIVATE_DIR = (
    r"C:\Users\user\trading\arb\ai_agent_trading_v1.0\v2_dual_quote_arb\data\backtest\1s"
)
DEFAULT_DATA_DIR = os.environ.get(
    "ARC_DEMO_DATA_DIR",
    str(_REPO_DATA_DIR if _REPO_DATA_DIR.exists() else _LEGACY_PRIVATE_DIR),
)


@dataclass
class ReplayConfig:
    symbol: str = "DOGE"
    data_dir: str = DEFAULT_DATA_DIR
    date: str = "20260419"
    bridge_url: str = "http://localhost:3000"
    # Signal params (matching v1.3 prod config)
    dt_entry_threshold_rate: float = 0.0017
    dc_entry_threshold_rate: float = 0.0017
    fee_rate: float = 0.00075
    slippage_rate: float = 0.00005
    initial_usdt: float = 1000.0
    initial_usdc: float = 1000.0
    replay_speed: float = 20.0  # 1s data played at 20 ticks/s


def load_pair(cfg: ReplayConfig) -> pd.DataFrame:
    """Load USDT + USDC parquet files and inner-join on timestamp.

    The v1.3 archive uses `open_time` (ms) as its time key and OHLCV columns.
    Normalize to a single `timestamp` key and expose `bid`/`ask`/`last` from
    the close price (spread is implicit in the 1s bar so we use close as mid).
    """
    base = Path(cfg.data_dir)
    usdt = pd.read_parquet(base / f"{cfg.symbol}USDT_{cfg.date}.parquet")
    usdc = pd.read_parquet(base / f"{cfg.symbol}USDC_{cfg.date}.parquet")

    for df_ in (usdt, usdc):
        if "timestamp" not in df_.columns and "open_time" in df_.columns:
            df_.rename(columns={"open_time": "timestamp"}, inplace=True)
        if "last" not in df_.columns and "close" in df_.columns:
            df_["last"] = df_["close"]
            df_["bid"] = df_["close"]
            df_["ask"] = df_["close"]

    usdt_cols = {c: f"{c}_usdt" for c in usdt.columns if c != "timestamp"}
    usdc_cols = {c: f"{c}_usdc" for c in usdc.columns if c != "timestamp"}
    df = usdt.rename(columns=usdt_cols).merge(
        usdc.rename(columns=usdc_cols), on="timestamp", how="inner"
    )
    log.info("Loaded %d joined ticks for %s %s", len(df), cfg.symbol, cfg.date)
    return df


def _mid(row: pd.Series, suffix: str) -> float:
    if f"bid_{suffix}" in row and f"ask_{suffix}" in row:
        return (row[f"bid_{suffix}"] + row[f"ask_{suffix}"]) / 2.0
    if f"mid_{suffix}" in row:
        return float(row[f"mid_{suffix}"])
    if f"close_{suffix}" in row:
        return float(row[f"close_{suffix}"])
    raise KeyError(f"No mid/bid/ask/close column for {suffix} in row")


def publish_signal(signal: ArbitrageSignal, url: str, session: requests.Session) -> bool:
    try:
        resp = session.post(
            f"{url}/signals/publish",
            json=signal.to_dict(),
            timeout=2.0,
        )
        if resp.status_code == 200:
            return True
        log.warning("Bridge replied %s: %s", resp.status_code, resp.text[:100])
    except requests.RequestException as e:
        log.warning("Bridge POST failed: %s", e)
    return False


def run(cfg: ReplayConfig) -> None:
    df = load_pair(cfg)
    sleep_per_tick = 1.0 / cfg.replay_speed

    usdt_bal = cfg.initial_usdt
    usdc_bal = cfg.initial_usdc
    published = 0
    session = requests.Session()

    # Wrap the whole replay loop in KeyboardInterrupt handling so that
    # CTRL+C during a live recording produces a clean one-line exit log
    # instead of a multi-line traceback visible on screen (camera hygiene).
    try:
        for _, row in df.iterrows():
            try:
                mid_usdt = _mid(row, "usdt")
                mid_usdc = _mid(row, "usdc")
            except KeyError as e:
                log.debug("Skip row: %s", e)
                continue

            decision = decide_v2(
                mid_usdt=mid_usdt,
                mid_usdc=mid_usdc,
                usdt=usdt_bal,
                usdc=usdc_bal,
                dt_entry_threshold_rate=cfg.dt_entry_threshold_rate,
                dc_entry_threshold_rate=cfg.dc_entry_threshold_rate,
                fee_rate=cfg.fee_rate,
                slippage_rate=cfg.slippage_rate,
            )

            if decision.action != ActionV2.HOLD:
                sig = ArbitrageSignal(
                    timestamp=time.time(),
                    producer_id="dual_quote_agent",
                    strategy="dual_quote_spread",
                    symbol=cfg.symbol,
                    action=SignalAction(decision.action.value),
                    premium_rate=decision.premium,
                    bid_price_a=float(row.get("bid_usdc", mid_usdc)),
                    ask_price_a=float(row.get("ask_usdc", mid_usdc)),
                    bid_price_b=float(row.get("bid_usdt", mid_usdt)),
                    ask_price_b=float(row.get("ask_usdt", mid_usdt)),
                    reason=decision.reason,
                    tier=SignalTier.RAW,
                    expected_profit_usd=decision.expected_profit_usd,
                )
                if publish_signal(sig, cfg.bridge_url, session):
                    published += 1
                    log.info(
                        "[%s] %s premium=%.4f%% profit=$%.4f (total published=%d)",
                        cfg.symbol, decision.action.value, decision.premium * 100,
                        decision.expected_profit_usd, published,
                    )

            time.sleep(sleep_per_tick)

        log.info("Replay complete. Total signals published: %d", published)
    except KeyboardInterrupt:
        log.info("Replay interrupted by user. Total signals published: %d", published)
        return


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="DOGE")
    p.add_argument("--date", default="20260419")
    p.add_argument("--bridge-url", default=os.getenv("ARC_BRIDGE_URL", "http://localhost:3000"))
    p.add_argument("--speed", type=float, default=20.0)
    p.add_argument("--threshold", type=float, default=0.0017,
                   help="DT/DC entry threshold rate (0.0017 = 0.17%%)")
    p.add_argument("--fee-rate", type=float, default=0.00075,
                   help="per-leg fee rate; 0 for demo so the gate doesn't "
                        "swallow micro-edges")
    p.add_argument("--slippage-rate", type=float, default=0.00005)
    args = p.parse_args()

    cfg = ReplayConfig(
        symbol=args.symbol,
        date=args.date,
        bridge_url=args.bridge_url,
        replay_speed=args.speed,
        dt_entry_threshold_rate=args.threshold,
        dc_entry_threshold_rate=args.threshold,
        fee_rate=args.fee_rate,
        slippage_rate=args.slippage_rate,
    )
    run(cfg)


if __name__ == "__main__":
    main()
