---
marp: true
theme: default
paginate: true
size: 16:9
---

# Signal Mesh on Arc
### An agent-to-agent nanopayment marketplace
### for crypto arbitrage signals

*Lablab.ai · Agentic Economy on Arc · 2026-04-25*

---

## The one-liner

> AI trading agents pay each other **sub-cent USDC** for arbitrage
> signals — settled on **Circle's Arc L1** where the amount you see
> transferred **is** the price the market set for that signal.

**Not a thought experiment.** Two producer agents (Kimchi Premium, Dual-Quote)
derived from live trading systems. One Gemini meta-agent. One on-chain
executor. 50+ USDC transfers per 2-min demo, every one of them
variable-priced by signal quality.

---

## The problem: gas eats the margin

On traditional L1s an "agent pays agent per signal" business model is
*mathematically* impossible:

| Chain | Per-tx gas | Signal price | Gas / price |
|---|---|---|---|
| Ethereum mainnet | $0.50 | $0.003 | **166×** — kills margin |
| Base / Solana | $0.001 | $0.003 | 33% — survives but tight |
| **Arc + Nanopayments** | **$0.00001** | $0.003 | **0.34%** — viable |

Arc is **the first L1 where a machine economy can actually operate at
machine-native frequency**.

---

## Why **Arc specifically** (not Base, not Solana)

Sub-cent transfers exist elsewhere. Arc has one thing no other chain does:

> **USDC is the native gas token.**

That collapses the architecture:

1. **Same-currency balance sheet.** Revenue and operating cost in the
   same denomination — no ETH/SOL treasury to rebalance.
2. **Self-sustaining agents.** An agent funds its own gas from fees it
   earned. No human top-up loop.
3. **Receipt = market.** Settlement amount is a function of signal
   quality. On-chain data encodes real information, not cron-ticks.

> *Every "agent economy" demo outside Arc has a hidden human re-funding
> the gas wallet. We don't.*

---

## Architecture

```
┌─── Producer agents (Python) ──────────────┐
│  • kimchi_agent       KRW/USDT premium    │
│  • dual_quote_agent   USDT/USDC spread    │
└──────────────┬─────────────────────────────┘
               │ POST /signals/publish (raw, $0.002)
               ▼
┌─── Arc Bridge (Node/TS, x402) ────────────┐
│  /signals/latest  /signals/premium        │
│  /tx/report       /signals/outcome        │
│  /producer/reliability                     │
└──────────────┬─────────────────────────────┘
               │
   ┌───────────┴───────────┐
   ▼                       ▼
┌─ Meta agent (Gemini+GBM) ─┐  ┌─ Executor agent ──────────┐
│ enrich → premium $0.01    │  │ pay + paper-trade + Arc   │
│ uses hit-rate feedback    │  │ USDC transfer settlement  │
└───────────────────────────┘  └───────────────────────────┘
```

All code lives at `github.com/…/signal-mesh-on-arc`.

---

## What is actually *agentic* here

Not "LLM wrapped around a script." Four real properties:

1. **Independent processes.** Each agent has its own wallet, its own
   market view, its own fee it pays and collects.
2. **Accountable pricing.** Every signal's settlement amount is
   `confidence × notional × premium × take_rate`. A bad signal
   literally earns less.
3. **Reputation feedback loop.** Executor reports realized PnL to
   `/signals/outcome`; meta-agent pulls `/producer/reliability` and
   **weights conflict resolution by each producer's hit-rate over the
   last 200 signals**. That is where the LLM earns its fee.
4. **No custody.** Agents hold their own keys (Circle Wallets roadmap).

---

## Circle product integration

| Product | Where it shows up |
|---|---|
| **Arc L1 testnet** | Every on-chain USDC transfer via `arc-testnet` RPC (ChainID 5042002) |
| **USDC** | Native 18-dec gas **and** 6-dec ERC-20 transfer unit — both |
| **x402 facilitator** | `bridge/src/index.ts` wires `x402-express` middleware on `/signals/*` endpoints |
| **Nanopayments path** | Variable-price settlements ≤ $0.01; EIP-3009 path wired; Gateway batching is the roadmap |
| **Developer Console** | Demo video shows a manual `transfer()` executed via Console UI on Arc testnet |
| **Circle Wallets** | Current demo uses EOA; Circle Wallet SDK wiring is a post-hackathon 2-hour swap |

---

## The ML: regime GBM trained on real data

Originality multiplier, not a gimmick:

- **Dataset.** 87 Binance spot pairs × 86 400 ticks/day (1 s resolution)
  — `~7.5M rows` of real USDT/USDC bid/ask data.
- **Features.** `{premium, mean, std, z-score, slope, sign-flips}` ×
  `{10 s, 30 s, 120 s}` — 16 features.
- **Labels.** 4-regime classifier (`noise` / `mean_revert` /
  `trending` / `event`), **causally labeled** (no forward-leak after
  2026-04-21 bug fix).
- **Use.** Meta-agent reads 120 s of recent premium, predicts regime,
  blends with LLM confidence. Regime is shown on every premium signal.

---

## Demo flow (what the video shows)

1. **`npm --prefix bridge run dev`** — bridge up.
2. **`python -m ml.regime_gbm`** — GBM trains in 2 min on 87 pairs.
3. **`python -m demo.run_demo --symbols DOGE,XRP,SOL --with-kimchi --duration 120`**
   - 3 dual-quote producers + 1 synthetic Kimchi producer
   - 1 meta-agent (Gemini + GBM blend)
   - 1 executor agent (variable-price settlement on Arc testnet)
4. Live counter overlays on screen:
   `t+XXs  raw=…  premium=…  onchain_tx=…`
5. Summary block prints **5 live Arc Explorer URLs**.
6. Cut to Circle Developer Console: execute one manual `transfer()`;
   cut to `testnet.arcscan.app` showing confirmation.

---

## What we'd do next (roadmap)

| Horizon | Unlock |
|---|---|
| **Week 1 post-hackathon** | EIP-3009 `transferWithAuthorization` + Gateway batching, Circle Wallets fully replacing EOAs |
| **Month 1** | ERC-8004 producer reputation, on-chain hit-rate commits |
| **Month 3** | Cross-exchange signal mesh: Coinbase, Kraken, OKX, Bybit producers |
| **Year 1** | **"Bloomberg Terminal for agents"** — any latency-sensitive feed (DeFi MEV tips, liquidation signals, prediction-market odds) priced per-read on Arc. Bloomberg is $24k/yr/seat; our unit is $0.01/signal × millions/day. |

---

## Ask

We're competing for **Online 1st ($2,500 USDC)** + **Product Feedback ($500 USDC)**.

- **Code:** `github.com/…/signal-mesh-on-arc` — all four agents, the
  bridge, the GBM trainer, the demo driver.
- **Product feedback:** 5 concrete pain points from building on Arc →
  `docs/PRODUCT_FEEDBACK.md` (x402 facilitator, `@circle/nanopay` SDK,
  dual-decimal footgun, Entity Secret rotation docs, Console code-copy).
- **Live demo:** runs in 2 minutes, no setup.

*Thank you. Questions to the chat.*
