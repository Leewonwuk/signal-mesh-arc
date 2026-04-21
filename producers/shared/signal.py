"""Unified ArbitrageSignal schema — published by both Kimchi and Dual-Quote producers.

This is the payload format consumed by the Arc Bridge and billed per signal via
x402 / Circle Nanopayments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional


class SignalAction(str, Enum):
    HOLD = "HOLD"
    # Kimchi (cross-exchange KRW/USDT)
    OPEN_UPBIT_SHORT_BINANCE_LONG = "OPEN_UPBIT_SHORT_BINANCE_LONG"
    OPEN_UPBIT_LONG_BINANCE_SHORT = "OPEN_UPBIT_LONG_BINANCE_SHORT"
    # Dual-Quote (intra-Binance USDT/USDC)
    TRADE_DT = "TRADE_DT"
    TRADE_DC = "TRADE_DC"
    CLOSE = "CLOSE"
    # Funding-rate basis (spot-long + perp-short). Added by F2 for Allocator RL.
    OPEN_FUNDING_LONG_SPOT_SHORT_PERP = "OPEN_FUNDING_LONG_SPOT_SHORT_PERP"
    CLOSE_FUNDING = "CLOSE_FUNDING"


class SignalTier(str, Enum):
    RAW = "raw"           # $0.002 — direct from producer
    PREMIUM = "premium"   # $0.01 — Meta Agent-annotated


@dataclass(slots=True)
class ArbitrageSignal:
    timestamp: float
    producer_id: str
    strategy: str                # "kimchi_premium" | "dual_quote_spread" | "meta"
    symbol: str
    action: SignalAction
    premium_rate: float          # decimal (0.0017 = 0.17%)
    bid_price_a: float
    ask_price_a: float
    bid_price_b: float
    ask_price_b: float
    reason: str
    tier: SignalTier = SignalTier.RAW
    confidence_score: Optional[float] = None
    notional_usd: Optional[float] = None
    expected_profit_usd: Optional[float] = None
    justification: Optional[str] = None  # Meta Agent (Gemini-generated)
    regime: Optional[str] = None          # "trending" | "mean_reverting" | "choppy"

    def price_usdc(self) -> float:
        return 0.002 if self.tier == SignalTier.RAW else 0.01

    def to_dict(self) -> dict:
        d = asdict(self)
        d["action"] = self.action.value
        d["tier"] = self.tier.value
        return d
