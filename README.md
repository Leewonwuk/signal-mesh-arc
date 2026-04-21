# Signal Mesh on Arc

> **Hackathon submission** — Agentic Economy on Arc (lablab.ai, 2026-04-20~26)

A machine-to-machine **trading signal marketplace** where AI agents pay each other in **USDC nanopayments on Arc** for arbitrage signals. Each signal costs `$0.002~0.01` and is settled onchain in a single Arc transaction — a price point that would be crushed by traditional gas costs.

---

## Why this matters (the margin story)

Traditional L1 gas (~$0.50+) vs signal price ($0.003):
- **Ethereum mainnet**: gas is **166×** the signal price → margin wiped 99.4%
- **Arc + Nanopayments**: overhead < $0.00001 → **< 0.34%** of signal price
- The "agent paying agent per signal" business model **only works on Arc**

---

## Why Arc (and not Base / Solana / Polygon)

Sub-cent transfers exist on Base and Solana today. That alone is not an answer.

**Arc is the only L1 where USDC is the native gas token.** For a signal
marketplace where agents both *earn* and *spend* in cents-per-second, that
collapses the architecture:

1. **Same-currency balance sheet.** A producer agent's revenue (USDC in) and
   its operating cost (USDC gas out) live in the same denomination. No
   ETH/SOL treasury to rebalance, no bridging, no FX exposure between
   "money made" and "money spent to make it."
2. **Self-sustaining agent finance.** An agent can fund its own gas purely
   from fees it earned. That is the requirement for fully autonomous,
   uncustodied agents operating indefinitely. On any other chain the
   operator has to top up the native token when it runs out.
3. **Variable-price settlement is legible.** The **amount** of each on-chain
   settlement in our demo is a function of signal confidence × notional ×
   premium — see `consumers/executor_agent/main.py::_price_signal`. Because
   amount and gas are both USDC, the receipt *is* the market.

**Counter-positioning tweet:** *"Every 'agent economy' demo outside Arc
has a hidden human re-funding the gas wallet. We don't."*

---

## What it does

```
┌─────────── Producers (Python) ────────────┐
│  Kimchi Signal Agent    (derived v1.1)    │  ← cross-exchange KRW↔USDT premium
│  Dual-Quote Signal Agent (derived v1.3)   │  ← intra-Binance USDT↔USDC spread
└─────────────────┬──────────────────────────┘
                  │ signals (HTTP/gRPC)
                  ▼
┌─────────── Arc Bridge (Node.js/TS) ───────┐
│  Signal Registry + Nanopayment settlement │  ← Arc RPC + USDC + Circle Nanopayments
└─────────────────┬──────────────────────────┘
                  │
                  ▼
┌─────────── Consumers ─────────────────────┐
│  Meta Agent (Gemini-powered, premium)     │  ← regime detection, NL reasoning
│  Executor Agent (paper-trades on signal)  │  ← proves signal is actionable
└────────────────────────────────────────────┘
```

---

## Stack

| Layer | Tech |
|---|---|
| Signal producers | Python 3.11 (reuses v1.1 / v1.3 trading modules) |
| Arc bridge | Node.js / TypeScript + Circle Nanopayments SDK |
| Smart contract | Arc L1 testnet (USDC stablecoin) |
| Meta agent | Python + Gemini API (Google AI Studio) — for $40k GCP bonus track |
| Transport | HTTP between producers ↔ bridge |
| Demo frontend | React + Vite (live tx stream view) |

---

## Hackathon requirement compliance

| Requirement | How we satisfy it |
|---|---|
| per-action ≤ $0.01 | Signal tiers: $0.002 (raw), $0.01 (Gemini-annotated premium) |
| 50+ onchain tx in demo | 2-minute demo drives 50+ USDC transfers on Arc testnet |
| "why gas would kill margin" | Onchain tx-by-tx cost breakdown included in submission |
| Gemini / Google AI Studio use | Meta agent uses Gemini for regime classification + NL justification |

---

## Directory map

```
hackerton/arc/
├── producers/           # Python: Kimchi + Dual-Quote signal sources
├── bridge/              # Node.js: Arc RPC + Nanopayments
├── consumers/           # Meta agent (Gemini) + Executor agent
├── shared/              # Signal schema, shared types
├── demo/                # Demo driver scripts, video recording helpers
├── docs/
│   ├── ARCHITECTURE.md
│   ├── pitch.md
│   └── judges/          # Giants' shoulders feedback rounds
└── contracts/           # If we deploy a registry contract
```

---

## Status

Currently: **Day 1 (2026-04-21)** — scaffolding + team research in parallel.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the technical design.
