"""Backfill 90 days of Binance funding-rate + spot + perp data into parquet.

Produces one parquet per symbol at <out-dir>/<symbol>_<days>d.parquet.
Row = one 8h funding cycle. Schema (see ALLOCATOR_RL_DESIGN.md §4):

    funding_time (ISO8601 UTC, divisible by 8h)
    symbol       (e.g. "DOGEUSDT")
    funding_rate (float, Binance decimal; 0.0001 == 0.01%/8h)
    mark_price   (float, mark at funding payment)
    spot_close   (float, Binance spot 8h kline close at funding_time)
    perp_close   (float, Binance perp 8h kline close at funding_time)
    basis_bps    (float, (perp - spot)/spot * 10000)
    notional_volume_usdt_8h (float, 8h spot volume in USDT for regime)

Public endpoints only (no auth required). If fapi.binance.com / api.binance.com
return 451/403, pass --api-host api1.binance.com.

Usage:
    python scripts/backfill_funding_data.py \
        --symbols DOGE,TRX,XRP,ADA,SOL \
        --days 90 \
        --out-dir data/funding
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

FUNDING_CYCLE_MS = 8 * 60 * 60 * 1000  # 8h
MAX_LIMIT = 1000

DEFAULT_FAPI = "https://fapi.binance.com"
DEFAULT_API = "https://api.binance.com"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "arc-allocator-backfill/1.0 (public data only)",
            "Accept": "application/json",
        }
    )
    return s


def _get(session: requests.Session, url: str, params: dict, retries: int = 4) -> list:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=20)
            if resp.status_code == 429:
                sleep_s = 2 ** attempt
                print(f"  [rate-limit] sleep {sleep_s}s", file=sys.stderr)
                time.sleep(sleep_s)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            last_err = e
            sleep_s = 1 + attempt
            print(f"  [retry {attempt + 1}/{retries}] {url} -> {e}; sleep {sleep_s}s",
                  file=sys.stderr)
            time.sleep(sleep_s)
    raise RuntimeError(f"GET {url} params={params} failed after {retries} retries: {last_err}")


def fetch_funding_rate(
    session: requests.Session,
    fapi_host: str,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """Fetch fundingRate history, paginating forward.

    Binance returns entries with fundingTime in ms and fundingRate as string.
    Each entry represents the funding PAID at fundingTime (00/08/16 UTC).
    """
    url = f"{fapi_host}/fapi/v1/fundingRate"
    rows: list[dict] = []
    cursor = start_ms
    seen: set[int] = set()
    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": MAX_LIMIT,
        }
        batch = _get(session, url, params)
        if not batch:
            break
        new_count = 0
        last_ft = cursor
        for item in batch:
            ft = int(item["fundingTime"])
            if ft in seen:
                continue
            seen.add(ft)
            rows.append(
                {
                    "funding_time_ms": ft,
                    "funding_rate": float(item["fundingRate"]),
                    "mark_price": float(item.get("markPrice") or 0.0) or float("nan"),
                }
            )
            last_ft = max(last_ft, ft)
            new_count += 1
        if new_count == 0:
            break
        # Advance past the last seen time to avoid duplicates
        cursor = last_ft + 1
        if len(batch) < MAX_LIMIT:
            break
    if not rows:
        return pd.DataFrame(columns=["funding_time_ms", "funding_rate", "mark_price"])
    df = pd.DataFrame(rows).sort_values("funding_time_ms").reset_index(drop=True)
    return df


def fetch_klines_8h(
    session: requests.Session,
    host: str,
    path: str,
    symbol: str,
    start_ms: int,
    end_ms: int,
) -> pd.DataFrame:
    """Fetch 8h klines from spot (api/v3/klines) or perp (fapi/v1/klines)."""
    url = f"{host}{path}"
    rows: list[list] = []
    cursor = start_ms
    last_open = -1
    while cursor < end_ms:
        params = {
            "symbol": symbol,
            "interval": "8h",
            "startTime": cursor,
            "endTime": end_ms,
            "limit": MAX_LIMIT,
        }
        batch = _get(session, url, params)
        if not batch:
            break
        for k in batch:
            open_ms = int(k[0])
            if open_ms <= last_open:
                continue
            rows.append(k)
            last_open = open_ms
        if len(batch) < MAX_LIMIT:
            break
        cursor = last_open + 1

    if not rows:
        return pd.DataFrame(
            columns=["open_ms", "close_price", "close_ms", "quote_volume"]
        )

    # Binance kline layout:
    # [0 openTime, 1 open, 2 high, 3 low, 4 close, 5 volume,
    #  6 closeTime, 7 quoteAssetVolume, 8 numTrades, 9 takerBuyBase,
    #  10 takerBuyQuote, 11 ignore]
    df = pd.DataFrame(
        [
            {
                "open_ms": int(k[0]),
                "close_price": float(k[4]),
                "close_ms": int(k[6]),
                "quote_volume": float(k[7]),
            }
            for k in rows
        ]
    ).sort_values("open_ms").reset_index(drop=True)
    return df


def build_symbol_frame(
    session: requests.Session,
    symbol: str,
    days: int,
    fapi_host: str,
    api_host: str,
) -> pd.DataFrame:
    pair = f"{symbol}USDT"
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    # Align end to the most recent completed 8h boundary
    end_ms = (now_ms // FUNDING_CYCLE_MS) * FUNDING_CYCLE_MS
    start_ms = end_ms - days * 24 * 60 * 60 * 1000

    print(f"[{pair}] fetching funding rate {days}d ({start_ms} -> {end_ms})")
    funding = fetch_funding_rate(session, fapi_host, pair, start_ms, end_ms)
    print(f"[{pair}]   funding rows: {len(funding)}")

    print(f"[{pair}] fetching perp klines 8h")
    perp = fetch_klines_8h(session, fapi_host, "/fapi/v1/klines", pair, start_ms, end_ms)
    print(f"[{pair}]   perp klines: {len(perp)}")

    print(f"[{pair}] fetching spot klines 8h")
    spot = fetch_klines_8h(session, api_host, "/api/v3/klines", pair, start_ms, end_ms)
    print(f"[{pair}]   spot klines: {len(spot)}")

    if funding.empty:
        raise RuntimeError(f"{pair}: no funding rate rows returned")

    # Binance reports fundingTime as the actual settlement ms which may drift
    # a few seconds from the 8h boundary; klines open on clean boundaries, so
    # snap funding_time_ms to the nearest 8h mark BEFORE joining.
    raw_ft = funding["funding_time_ms"].astype("int64")
    snapped = ((raw_ft + FUNDING_CYCLE_MS // 2) // FUNDING_CYCLE_MS) * FUNDING_CYCLE_MS
    drift_s = (raw_ft - snapped).abs().max() / 1000.0
    if drift_s > 60:
        print(f"[{pair}] warning: max funding-time drift from 8h boundary = {drift_s:.1f}s")
    funding = funding.copy()
    funding["funding_time_ms"] = snapped
    funding = funding.drop_duplicates(subset=["funding_time_ms"], keep="first")

    # Each funding_time IS a kline open boundary (00/08/16 UTC). Join by open_ms.
    perp_ren = perp.rename(
        columns={"open_ms": "funding_time_ms", "close_price": "perp_close"}
    )[["funding_time_ms", "perp_close"]]
    spot_ren = spot.rename(
        columns={
            "open_ms": "funding_time_ms",
            "close_price": "spot_close",
            "quote_volume": "notional_volume_usdt_8h",
        }
    )[["funding_time_ms", "spot_close", "notional_volume_usdt_8h"]]

    df = funding.merge(perp_ren, on="funding_time_ms", how="left").merge(
        spot_ren, on="funding_time_ms", how="left"
    )

    # If mark_price is missing, fall back to perp_close
    df["mark_price"] = df["mark_price"].where(df["mark_price"].notna(), df["perp_close"])

    df["basis_bps"] = (
        (df["perp_close"] - df["spot_close"]) / df["spot_close"] * 10000.0
    )

    df["symbol"] = pair
    df["funding_time"] = pd.to_datetime(
        df["funding_time_ms"], unit="ms", utc=True
    ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    bad = df["funding_time_ms"] % FUNDING_CYCLE_MS
    assert (bad == 0).all(), f"{pair}: {(bad != 0).sum()} rows not on 8h boundary post-snap"

    # Drop rows missing any kline data (symbol may have listed mid-window)
    pre = len(df)
    df = df.dropna(subset=["spot_close", "perp_close"]).reset_index(drop=True)
    if len(df) < pre:
        print(f"[{pair}] dropped {pre - len(df)} rows missing spot/perp klines")

    cols = [
        "funding_time",
        "symbol",
        "funding_rate",
        "mark_price",
        "spot_close",
        "perp_close",
        "basis_bps",
        "notional_volume_usdt_8h",
    ]
    return df[cols]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--symbols",
        default="DOGE,TRX,XRP,ADA,SOL",
        help="Comma-separated base symbols (USDT quote appended automatically).",
    )
    p.add_argument("--days", type=int, default=90, help="Lookback in days (default 90).")
    p.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent.parent / "data" / "funding"),
        help="Output directory for parquet files.",
    )
    p.add_argument(
        "--fapi-host",
        default=DEFAULT_FAPI,
        help=f"Binance perp host (default {DEFAULT_FAPI}).",
    )
    p.add_argument(
        "--api-host",
        default=DEFAULT_API,
        help=(
            f"Binance spot host (default {DEFAULT_API}). "
            "Pass https://api1.binance.com etc. on 451/403."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    symbols: Iterable[str] = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = _session()
    written: list[tuple[str, Path, int]] = []
    for sym in symbols:
        df = build_symbol_frame(session, sym, args.days, args.fapi_host, args.api_host)
        out_path = out_dir / f"{sym}_{args.days}d.parquet"
        df.to_parquet(out_path, engine="pyarrow", index=False)
        print(f"[{sym}USDT] wrote {len(df)} rows -> {out_path}")
        written.append((sym, out_path, len(df)))

    print("\n=== Summary ===")
    for sym, path, n in written:
        print(f"  {sym}USDT : {n:4d} rows  {path}")

    # Sanity: print first 5 rows of DOGE
    doge_path = out_dir / f"DOGE_{args.days}d.parquet"
    if doge_path.exists():
        print("\n=== DOGE first 5 rows ===")
        doge = pd.read_parquet(doge_path)
        with pd.option_context("display.max_columns", None, "display.width", 200):
            print(doge.head().to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
