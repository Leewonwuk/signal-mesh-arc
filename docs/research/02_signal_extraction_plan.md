# Signal Extraction Plan (Team Member 2 Output)

> Produced by research agent, 2026-04-21. Source: v1.1 + v1.3 codebase analysis.

## Summary table

| Aspect | Kimchi v1.1 | Dual-Quote v1.3 |
|---|---|---|
| **Signal function** | `calc_edge()` + `SignalEngine.decide()` | `decide_v2()` |
| **Reusable lines** | ~200 | ~150 |
| **Exec code to strip** | 1,500+ | 2,000+ |
| **Main loop freq** | 10+ Hz | 20 Hz |
| **Adaptation effort** | 4-5h | 4-5h |

## v1.1 (Kimchi) — Files to reuse

| File | Status | Notes |
|---|---|---|
| `src/models.py` | ✅ verbatim | `OrderBookTop`, `SpreadInput`, `EdgeResult`, `SignalDecision` — zero deps |
| `src/strategy/spread_calc.py` | ✅ verbatim | `calc_edge()` — pure function |
| `src/strategy/signal.py` | ✅ verbatim | `SignalEngine.decide()` — stateful dataclass, no exchange coupling |
| `src/marketdata.py` | 🔧 strip | Keep `snapshot()`; strip Upbit (keep Binance REST fallback for single-leg variant) |
| `src/exchanges/binance_client.py`, `binance_ws.py` | 🔧 strip | Keep `fetch_top()`; strip order execution |
| `src/exchanges/upbit_*` + `fx_upbit.py` | ❌ | Cross-exchange stuff (but `fx_upbit.fetch_fx_krw_per_usdt()` is useful standalone) |
| `src/execution/`, `state/`, `logging/` | ❌ | All execution/state/DB |

## v1.3 (Dual-Quote) — Files to reuse

| File | Status | Notes |
|---|---|---|
| `src/allocator_v2.py` | ✅ verbatim | `decide_v2()` — pure function, stateless |
| `src/config_v2.py` | ✅ verbatim | `V12ConfigV2` + YAML loader |
| `src/price_util.py` | 🔧 strip | Backtest-only `v12_leg_mids()` — for live use `PriceFeed.get_mid()` |
| `src/price_feed.py` | 🔧 strip | Keep `_book_ticker_loop()` + `get_mid()` / `get_bid_ask()`; strip `_user_data_loop()` |
| `src/live_engine_v2.py` | ❌ | All execution state machine |
| `src/live_v2_main.py` | ❌ | Orchestration |
| backtest/, global_lock, ws_order_client, portfolio_v2 | ❌ | |

## Signal function signatures

### Kimchi path
```python
# spread_calc.calc_edge(snapshot, symbol, trade_size_base, ...) -> EdgeResult
# signal.SignalEngine.decide(edge, has_open_position, position_open_at) -> SignalDecision
```
Actions: `OPEN_UPBIT_SHORT_BINANCE_LONG`, `OPEN_UPBIT_LONG_BINANCE_SHORT`, `CLOSE`, `HOLD`

### Dual-Quote path
```python
# allocator_v2.decide_v2(mid_usdt, mid_usdc, usdt, usdc, thresholds, ...) -> DecisionV2
```
Actions: `ActionV2.TRADE_DT` (USDC→USDT), `ActionV2.TRADE_DC` (USDT→USDC), `ActionV2.HOLD`

## Proposed unified `ArbitrageSignal` schema

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class SignalAction(str, Enum):
    HOLD = "HOLD"
    OPEN_UPBIT_SHORT_BINANCE_LONG = "OPEN_UPBIT_SHORT_BINANCE_LONG"
    OPEN_UPBIT_LONG_BINANCE_SHORT = "OPEN_UPBIT_LONG_BINANCE_SHORT"
    TRADE_DT = "TRADE_DT"
    TRADE_DC = "TRADE_DC"
    CLOSE = "CLOSE"

@dataclass(slots=True)
class ArbitrageSignal:
    timestamp: float
    producer_id: str          # "kimchi_agent" / "dual_quote_agent"
    strategy: str             # "kimchi_premium" / "dual_quote_spread"
    symbol: str
    action: SignalAction
    premium_rate: float       # decimal rate
    bid_price_a: float        # Leg A
    ask_price_a: float
    bid_price_b: float        # Leg B
    ask_price_b: float
    reason: str
    confidence_score: Optional[float] = None
    notional_usd: Optional[float] = None
    expected_profit_usd: Optional[float] = None
```

## Landmines (silent coupling)

1. **Global state in main loops** — v1.1 `multi_main.py` has concurrent portfolio tracking; v1.3 has `GlobalTradeLock` singleton
2. **Hardcoded file paths** — both write CSV logs to `logs/`; don't replicate
3. **Telegram notifications** wired into execution loops — strip imports
4. **DB writes** — v1.3 writes `engine_state_{sym}.json` for crash recovery; do NOT inherit
5. **FX rate dep** — v1.1 pulls live KRW/USDT from asyncio external API; extract as standalone 60s-TTL cached
6. **Binance auth** — v1.1 REST-only safe; v1.3 `BinanceTradingClient` needs `api_secret` (disable trading endpoints; use api_key only)
7. **Config validators** — both check `mode=="live"` + `enable_live_orders`; override: `mode="signal_only"`

## Full producer main.py samples

*(See full agent report in conversation for complete Python samples — ~200 lines each for Kimchi and Dual-Quote producers, ready to adapt)*

Key loop pattern:
```python
while True:
    snapshot = market_data.snapshot(...)
    decision = decide(...)
    if decision.action != HOLD:
        signal = ArbitrageSignal(...)
        post_signal_to_arc(signal, arc_url)
    time.sleep(poll_interval)
```
