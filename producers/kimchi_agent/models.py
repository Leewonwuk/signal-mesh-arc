"""Copied verbatim from v1.1 (v1_kimchi_premium/src/models.py) — pure dataclasses."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass(slots=True)
class OrderBookTop:
    exchange: str
    symbol: str
    bid: float
    ask: float
    ts: str

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0


@dataclass(slots=True)
class SpreadInput:
    upbit_krw: OrderBookTop
    binance_usdt: OrderBookTop
    fx_krw_per_usdt: float
    fee_upbit_rate: float
    fee_binance_rate: float
    slippage_upbit_rate: float
    slippage_binance_rate: float


@dataclass(slots=True)
class EdgeResult:
    symbol: str
    upbit_to_binance_edge_rate: float
    binance_to_upbit_edge_rate: float
    upbit_to_binance_transfer_fee_rate: float
    binance_to_upbit_transfer_fee_rate: float
    upbit_mid_krw: float
    binance_mid_krw: float
    fx_krw_per_usdt: float


@dataclass(slots=True)
class SignalDecision:
    action: str
    reason: str
    edge_rate: float = 0.0
