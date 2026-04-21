# Producers — Python signal agents

Kimchi (v1.1-derived) and Dual-Quote (v1.3-derived) signal producers. Stateless, read-only on their upstream exchanges, publish to the Arc bridge over HTTP.

## Replay data provenance (important)

The dual-quote producer replays **1-second parquet snapshots captured from the submitter's live v1.3 production arbitrage bot** (the one currently running on EC2 against Binance spot). Concretely:

- Source: the same EC2 bot the submitter runs in prod — 9 coins (ADA/BNB/DOGE/SOL/TRX/XRP/APT/FET/WLD), pool ≈ $1,977 USDT, threshold 0.17%, stop-loss 0.25%.
- Default capture: `20260419` under `ai_agent_trading_v1.0/v2_dual_quote_arb/data/backtest/1s/`.
- Why replay, not live WS: demo determinism and reproducibility for the hackathon judge. The class in `producers/dual_quote_agent/main.py` is `ParquetReplayFeed`; replace with the v1.3 `PriceFeed` for true live.

This is why the signal tape on the dashboard is *not* synthetic — it is the real book the prod bot saw that day, streaming at 20× wall-clock.
