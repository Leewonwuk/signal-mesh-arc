"""Copied verbatim from v1.3 (v2_dual_quote_arb/src/allocator_v2.py) — pure function."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionV2(str, Enum):
    HOLD = "HOLD"
    TRADE_DT = "TRADE_DT"  # USDC → USDT direction
    TRADE_DC = "TRADE_DC"  # USDT → USDC direction


@dataclass
class DecisionV2:
    action: ActionV2
    premium: float
    reason: str
    expected_profit_usd: float = 0.0


def decide_v2(
    mid_usdt: float,
    mid_usdc: float,
    usdt: float,
    usdc: float,
    dt_entry_threshold_rate: float,
    dc_entry_threshold_rate: float,
    fee_rate: float,
    slippage_rate: float,
    entry_split_fraction: float = 0.25,
    exec_dc_premium: float | None = None,
    exec_dt_premium: float | None = None,
) -> DecisionV2:
    if mid_usdc <= 0 or mid_usdt <= 0:
        return DecisionV2(ActionV2.HOLD, 0.0, "zero_price")

    mid_premium = (mid_usdt - mid_usdc) / mid_usdc
    total_fee_rate = 2.0 * (fee_rate + slippage_rate)
    total_stable = usdt + usdc

    dt_prem = exec_dt_premium if exec_dt_premium is not None else (mid_premium if mid_premium > 0 else 0.0)
    if dt_prem > dt_entry_threshold_rate:
        if total_stable < 0.01:
            return DecisionV2(ActionV2.HOLD, dt_prem, "dt_no_stable")
        notional = total_stable * entry_split_fraction
        expected = notional * (dt_prem - total_fee_rate)
        if expected > 0:
            return DecisionV2(ActionV2.TRADE_DT, dt_prem, "dt_premium_profitable", expected)
        return DecisionV2(ActionV2.HOLD, dt_prem, "dt_premium_fee_exceeds_profit")

    dc_prem = exec_dc_premium if exec_dc_premium is not None else (-mid_premium if mid_premium < 0 else 0.0)
    if dc_prem > dc_entry_threshold_rate:
        if total_stable < 0.01:
            return DecisionV2(ActionV2.HOLD, dc_prem, "dc_no_stable")
        notional = total_stable * entry_split_fraction
        expected = notional * (dc_prem - total_fee_rate)
        if expected > 0:
            return DecisionV2(ActionV2.TRADE_DC, dc_prem, "dc_premium_profitable", expected)
        return DecisionV2(ActionV2.HOLD, dc_prem, "dc_premium_fee_exceeds_profit")

    return DecisionV2(ActionV2.HOLD, mid_premium, "below_threshold")
