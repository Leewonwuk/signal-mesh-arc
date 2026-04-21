"""Copied from v1.1 (v1_kimchi_premium/src/strategy/spread_calc.py) — import path adapted."""
from __future__ import annotations

from .models import EdgeResult, SpreadInput


def calc_edge(
    snapshot: SpreadInput,
    symbol: str,
    trade_size_base: float,
    transfer_fee_upbit_to_binance_base: float = 0.0,
    transfer_fee_binance_to_upbit_base: float = 0.0,
) -> EdgeResult:
    upbit_mid_krw = snapshot.upbit_krw.mid
    binance_mid_krw = snapshot.binance_usdt.mid * snapshot.fx_krw_per_usdt
    notional_krw = upbit_mid_krw * trade_size_base

    total_cost_rate = (
        snapshot.fee_upbit_rate
        + snapshot.fee_binance_rate
        + snapshot.slippage_upbit_rate
        + snapshot.slippage_binance_rate
    )
    if notional_krw <= 0:
        raise ValueError("trade_size_base must produce positive notional")

    upbit_to_binance_transfer_fee_rate = (
        (transfer_fee_upbit_to_binance_base * snapshot.binance_usdt.ask * snapshot.fx_krw_per_usdt)
        / notional_krw
    )
    binance_to_upbit_transfer_fee_rate = (
        (transfer_fee_binance_to_upbit_base * snapshot.upbit_krw.ask) / notional_krw
    )

    upbit_to_binance_raw = (
        snapshot.upbit_krw.bid - (snapshot.binance_usdt.ask * snapshot.fx_krw_per_usdt)
    ) / upbit_mid_krw
    upbit_to_binance_edge = (
        upbit_to_binance_raw - total_cost_rate - upbit_to_binance_transfer_fee_rate
    )

    binance_to_upbit_raw = (
        (snapshot.binance_usdt.bid * snapshot.fx_krw_per_usdt) - snapshot.upbit_krw.ask
    ) / binance_mid_krw
    binance_to_upbit_edge = (
        binance_to_upbit_raw - total_cost_rate - binance_to_upbit_transfer_fee_rate
    )

    return EdgeResult(
        symbol=symbol,
        upbit_to_binance_edge_rate=upbit_to_binance_edge,
        binance_to_upbit_edge_rate=binance_to_upbit_edge,
        upbit_to_binance_transfer_fee_rate=upbit_to_binance_transfer_fee_rate,
        binance_to_upbit_transfer_fee_rate=binance_to_upbit_transfer_fee_rate,
        upbit_mid_krw=upbit_mid_krw,
        binance_mid_krw=binance_mid_krw,
        fx_krw_per_usdt=snapshot.fx_krw_per_usdt,
    )
