# Signal Mesh on Arc

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/node-18%2B-green)](https://nodejs.org/)
[![Arc testnet](https://img.shields.io/badge/Arc-testnet-7b61ff)](https://testnet.arcscan.app/)
[![lablab.ai](https://img.shields.io/badge/hackathon-Agentic%20Economy%20on%20Arc-orange)](https://lablab.ai/)

> **Hackathon submission** — [Agentic Economy on Arc](https://lablab.ai/) · lablab.ai · 2026-04-20 ~ 26

An **agent-to-agent signal marketplace** where specialist AI trading agents pay each other sub-cent USDC for arbitrage signals — settled onchain, every tick, on Arc. Signal price is $0.002 – $0.01, and the gas is denominated in the same USDC. On any other L1 that margin collapses.

- 📄 **Full submission**: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- 🎬 **Video script**: [`docs/VIDEO.md`](docs/VIDEO.md)
- 🚀 **Live dashboard**: https://signal-mesh.vercel.app
- ⚡ **Quick start**: [`QUICKSTART.md`](QUICKSTART.md)

---

## TL;DR — three things to remember

1. **USDC-as-gas closes the loop.** Signal priced in USDC, paid in USDC, gas in USDC. No human re-funding a second-asset wallet. Every other chain has a hidden human.
2. **60+ sub-cent A2A tx in a 5-minute demo.** EIP-3009 + x402 paywall + variable on-chain price that encodes signal quality. Real settlements on Arc testnet, verifiable on `testnet.arcscan.app`.
3. **RL capital allocator ties the empirical optimum on a walk-forward hold-out.** Tabular Q-learning over 3 arb strategies, audited by a Sutton-school adversarial agent (`p=0.49` vs ALL_V2, `p=0.012` vs DIVERSIFY). Receipts in `SUBMISSION.md §11.b`.

---

## Why Arc (and not Base / Solana / Polygon)

Sub-cent transfers exist on Base and Solana today. That alone is not an answer.

**Arc is the only L1 where USDC is the native gas token.** For a marketplace where agents both *earn* and *spend* in cents-per-second, that collapses the architecture:

1. **Same-currency balance sheet.** A producer's revenue (USDC in) and its gas (USDC out) live in the same denomination. No ETH/SOL treasury to rebalance, no FX between "money made" and "money spent to make it."
2. **Self-sustaining agent finance.** An agent can fund its own gas from fees it earned. That is the requirement for fully autonomous, uncustodied agents. On any other chain an operator has to top up the native token.
3. **Variable-price settlement is legible.** The on-chain **amount** of each settlement is a function of signal confidence × notional × premium — see `consumers/executor_agent/pricing_policy.py::choose_price`. Amount and gas are both USDC, so the receipt *is* the market.

> *"Every 'agent economy' demo outside Arc has a hidden human re-funding the gas wallet. We don't."*

---

## Architecture

```
┌─────────── Producers (Python) ────────────┐
│  Kimchi Signal Agent      (derived v1.1)  │  KRW ↔ USDT cross-exchange premium
│  Dual-Quote Signal Agent  (derived v1.3)  │  intra-Binance USDT ↔ USDC spread
│  Funding Agent            (derived v3)    │  perp funding-rate basis
└─────────────────┬──────────────────────────┘
                  │ signals over HTTP
                  ▼
┌─────────── Arc Bridge (Node.js/TS) ───────┐
│  Signal registry + nanopayment settlement │  Arc RPC · Circle Nanopayments SDK
│  /policy/persona · /allocation · /tx      │  EIP-3009 · x402 paywall
└─────────────────┬──────────────────────────┘
                  │
                  ▼
┌─────────── Consumers ─────────────────────┐
│  Meta Agent       (Gemini, premium tier)  │  regime detection + NL justification
│  Executor Agent   (paper-trades signals)  │  proves the signal is actionable
│  Capital Allocator (tabular Q-learning)   │  routes capital across 3 strategies
└────────────────────────────────────────────┘
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for sequence diagrams and the ML pipeline.

---

## Stack

| Layer | Tech |
|---|---|
| Signal producers | Python 3.11, pandas, pyarrow (replay from shipped 1s parquets) |
| Arc bridge | Node.js 18 / TypeScript + Circle Nanopayments SDK |
| Settlement | Arc L1 testnet · USDC · EIP-3009 `transferWithAuthorization` |
| Meta agent | Gemini API (Google AI Studio) — $40k GCP bonus track |
| ML | sklearn `GradientBoostingClassifier` (regime) + tabular Q-learning (allocator) |
| Dashboard | React + Vite + TypeScript, hosted on Vercel |

---

## Quick start

Full prerequisites (Circle account, Gemini key, `.env`) are in [`QUICKSTART.md`](QUICKSTART.md). Once those are set:

```bash
# 1) Install
pip install -r requirements.txt
npm --prefix bridge ci
npm --prefix dashboard ci

# 2) Three terminals
npm --prefix bridge    run dev                                    # T1: Arc bridge
npm --prefix dashboard run dev                                    # T2: live UI
python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 120     # T3: driver
```

The demo driver spawns one dual-quote producer per symbol, one meta agent, one executor, and one capital allocator. After 2 minutes it prints a summary pulled from `/health` and `/tx/recent`. Expect **60+ USDC settlements on Arc testnet** (verifiable on [testnet.arcscan.app](https://testnet.arcscan.app/)).

> The repo ships 135 MB of 1s parquet replay data for DOGE/XRP/SOL × USDT/USDC (date `20260419`) in `data/v1_3_replay/`, so the producers run out of the box without any external data source.

---

## Hackathon requirement compliance

| Requirement | Evidence |
|---|---|
| per-action ≤ $0.01 | Signal tiers: `$0.002` raw, `$0.01` Gemini-annotated premium — `consumers/executor_agent/pricing_policy.py::choose_price` |
| 50+ onchain tx in demo | Default 2-min demo → 60+ USDC transfers on Arc testnet |
| "why gas would kill margin" | Tx-by-tx cost breakdown in [`docs/SUBMISSION.md §3`](docs/SUBMISSION.md) |
| Gemini / Google AI Studio | Meta agent uses Gemini for regime classification + NL justification |
| Originality hook | Regime-conditioned RL capital allocator with walk-forward hold-out audit |

---

## Directory map

```
hackerton/arc/
├── producers/           # Python: kimchi, dual_quote, funding (v3 vendored)
├── consumers/           # Meta agent (Gemini), executor, capital allocator
├── bridge/              # Node.js: Arc RPC + Nanopayments + policy/outcome endpoints
├── dashboard/           # React+Vite UI (tx stream, policy heatmap, fee explorer)
├── ml/                  # Regime GBM + Q-table persistence
├── scripts/             # Pretrain, backtest, smoke-test utilities
├── demo/                # Demo driver, recording helpers
├── data/v1_3_replay/    # 1s parquet replay (DOGE/XRP/SOL × USDT/USDC, 135 MB)
├── shared/              # Signal schema shared across producers/consumers
└── docs/                # SUBMISSION, VIDEO, ARCHITECTURE, judges feedback rounds
```

---

## Receipts

- **Walk-forward backtest**: TrainedQ ties `ALL_V2` on 47-tick hold-out (`$7.61` vs `$9.44`, `p=0.49` vs ALL_V2, `p=0.012` vs DIVERSIFY). See `scripts/backtest_allocator.py` and [`docs/SUBMISSION.md §11.b`](docs/SUBMISSION.md).
- **Giants-on-shoulders rounds**: Sutton-school adversarial review in [`docs/GIANTS_SHOULDERS_ALLOCATOR_REVIEW.md`](docs/GIANTS_SHOULDERS_ALLOCATOR_REVIEW.md); Karpathy/Garry Tan pitch reviews threaded through [`docs/SUBMISSION.md`](docs/SUBMISSION.md).
- **ML backtest report**: [`docs/BACKTEST_ML_REPORT.md`](docs/BACKTEST_ML_REPORT.md) · rule-based v2: [`docs/BACKTEST_RULES_V2_REPORT.md`](docs/BACKTEST_RULES_V2_REPORT.md).

---

## License & contact

Hackathon submission, all-rights-reserved during judging. Contact: **skyskywin@gmail.com** · GitHub: [@Leewonwuk](https://github.com/Leewonwuk)
