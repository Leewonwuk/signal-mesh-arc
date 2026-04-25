# AlphaLoop

*The agent-to-agent **alpha** **loop** on Arc — a learned Q-policy closes the payment loop between four trading agents, variably priced by signal quality, fed by a live v1.3 arb bot running right now on EC2.*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Node 18+](https://img.shields.io/badge/node-18%2B-green)](https://nodejs.org/)
[![Arc testnet](https://img.shields.io/badge/Arc-testnet-7b61ff)](https://testnet.arcscan.app/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
[![lablab.ai](https://img.shields.io/badge/hackathon-Agentic%20Economy%20on%20Arc-orange)](https://lablab.ai/)

> **Hackathon submission** — [Agentic Economy on Arc](https://lablab.ai/) · lablab.ai · 2026-04-20 ~ 26
> **Track**: 🤖 Agent-to-Agent Payment **Loop** (primary)

## 🧾 STATUS (verify in 60 seconds)

| Signal | Value | Verify |
|---|---|---|
| ERC-8004 Registry contract | [`0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab`](https://testnet.arcscan.app/address/0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab) | Arc testnet, chainId 5042002 · **source code verified** on Arcscan (click → Code tab) |
| On-chain `AgentRegistered` events | **4** (one per wallet) | [`docs/evidence/erc8004_registry.json`](docs/evidence/erc8004_registry.json) |
| Settlement tx burst | **150** variably-priced USDC, $0.0005–$0.0099 | [`docs/evidence/batch_tx_hashes.txt`](docs/evidence/batch_tx_hashes.txt) |
| Merkle root (150-tx audit manifest) | `400039d5…05b80` | `make verify` or [`merkle_root.txt`](docs/evidence/merkle_root.txt) |
| Live dashboard | [`signal-mesh.vercel.app`](https://signal-mesh.vercel.app) | HTTP 200 |
| Agent cards (ERC-8004 registration-v1) | 4 served at `/.well-known/agent-card/<role>` | [`executor-agent.json`](https://signal-mesh.vercel.app/.well-known/agent-card/executor-agent.json) |
| Per-action pricing range | **$0.0005 – $0.010** (variable, 60/30/10 tier) | `scripts/circle_batch_settle.js::sampleAmount` |
| License | MIT | [`LICENSE`](./LICENSE) |


**AlphaLoop is the only entry in Track 2 whose demo is fed by a live, profit-generating production trading bot running right now on EC2.** Four specialist AI agents pay each other sub-cent USDC for arbitrage signals, amounts **varying per signal quality from $0.0005 to the $0.010 per-action cap**. Arc's USDC-as-gas closes the loop without a human refiller. A learned Q-policy picks which trading strategy gets to trade — and its Round 2 ties the empirical optimum on walk-forward out-of-sample.

- 📄 **Full submission**: [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- 🎬 **Video script**: [`docs/VIDEO.md`](docs/VIDEO.md)
- 🚀 **Live dashboard**: [signal-mesh.vercel.app](https://signal-mesh.vercel.app) · pitch video shows the same UI backed by the local bridge for real-time data
- ⚡ **Quick start**: [`QUICKSTART.md`](QUICKSTART.md)
- 🏷 **Why "AlphaLoop"?** **Alpha** = the trading moat (a live production arb bot generates the signal flow). **Loop** = the agent-to-agent payment loop named in the hackathon track. Our pitch: *close the alpha loop with a learned policy, on Arc*.

---

## TL;DR — three things to remember

1. **Only entry in Track 2 with a live production revenue system feeding the demo.** The dual-quote producer replays 1-second OHLCV from my **v1.3 arb bot running on EC2 right now** — 9 coins, pool ≈ $1,977 USDT, threshold 0.17%, stop-loss 0.25%. This hackathon submission is **layer 2 on a real trading system**, not a demo built to win a hackathon. Every signal the agents trade is a price the production bot actually saw on 2026-04-19.
2. **Round 1, our Q-learner lost to a one-line if-statement.** A Sutton-school adversarial review caught a reward-hacking bug in the reward function. Round 2 **ties the empirical optimum** on a 47-tick walk-forward hold-out (`p=0.49` vs ALL_V2, `p=0.012` vs DIVERSIFY). Fail → diagnose → fix → receipt. Full breakdown in `SUBMISSION.md §11.b.1`, reproducible from committed data.
3. **150+ variably-priced agent-to-agent tx + 5 on-chain ERC-8004 identity events land on Arc testnet per demo run.** Settlement amounts vary $0.0005–$0.010 per signal quality (60/30/10 low/mid/high distribution). Circle's Developer API executes the transfers; `(hash, amount)` records in [`docs/evidence/batch_tx_hashes.txt`](docs/evidence/batch_tx_hashes.txt), Merkle root in [`docs/evidence/merkle_root.txt`](docs/evidence/merkle_root.txt). Our `AlphaLoopAgentRegistry` at `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` emitted 5 `AgentRegistered` events (3 producers · 1 meta · 1 executor) — see [`docs/evidence/erc8004_registry.json`](docs/evidence/erc8004_registry.json). All verifiable on `testnet.arcscan.app`. Arc's USDC-as-gas is the only reason the marginal economics work — on any other L1, the gas eats the signal.

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

The demo driver spawns one dual-quote producer per symbol, one meta agent, one executor (paper mode for marketplace dynamics), and one capital allocator. For the **on-chain evidence burst** (150 variably-priced real USDC settlements on Arc testnet, verifiable on [testnet.arcscan.app](https://testnet.arcscan.app/)), run:

```bash
node scripts/circle_batch_settle.js --count 150 --rate 3
```

> The repo ships 135 MB of 1s parquet replay data for DOGE/XRP/SOL × USDT/USDC (date `20260419`) in `data/v1_3_replay/`, so the producers run out of the box without any external data source.

---

## Hackathon requirement compliance

| Requirement | Evidence |
|---|---|
| per-action ≤ $0.01 (**real variable pricing**) | On-chain tx amounts sampled from executor's signal-quality distribution, **varying $0.0005 – $0.010** per tx (60/30/10 low/mid/high tiers). Source of truth: `consumers/executor_agent/pricing_policy.py::choose_price`. Evidence: 150 `(hash, amount)` records in `docs/evidence/batch_tx_hashes.txt`. |
| 50+ onchain tx in demo | `node scripts/circle_batch_settle.js --count 150 --rate 3` → **150 variably-priced USDC tx** on Arc testnet via Circle Developer API |
| "why gas would kill margin" | Tx-by-tx cost breakdown in [`docs/SUBMISSION.md §3`](docs/SUBMISSION.md) + `WhyArcCard` visual on dashboard |
| Gemini / Google AI Studio | Meta agent uses Gemini 2.5 Flash for regime classification + NL justification (stub fallback on quota) |
| Originality hook | Regime-conditioned **RL capital allocator** with walk-forward hold-out audit — Round 1 lost to a one-line rule, Round 2 ties the empirical optimum (§11.b) |
| Agent identity & reputation | ERC-8004-compatible: 4 canonical Arc addresses (`scripts/circle_batch_settle.js::WALLETS`) + realized-PnL-weighted reputation at `GET /producer/reliability` — see SUBMISSION §5.a |
| MIT license | [`LICENSE`](./LICENSE) |

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
