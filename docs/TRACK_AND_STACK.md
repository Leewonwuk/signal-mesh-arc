# Track & Stack Decisions

## 🎯 Primary Track: 🤖 Agent-to-Agent Payment Loop

> "Create autonomous agents that pay and receive value in real time, proving machine-to-machine commerce without batching or custodial control."

**Why this track**: our Kimchi + Dual-Quote producer agents sell signals; Meta + Executor consumer agents buy them. Every signal = one real-time, non-custodial, non-batched USDC nanopayment. Perfect fit.

**Secondary alignment**: 🪙 Per-API Monetization (signal producers are effectively monetized APIs) + 🧮 Usage-Based Compute (Meta agent billed per Gemini call).

---

## 🔒 Required Stack (all included)

| Tech | Our use |
|---|---|
| **Arc (L1)** | All signal settlements. EVM-compatible. |
| **USDC** | Signal price unit + gas token on Arc |
| **Circle Nanopayments** | Sub-cent, high-frequency settlement primitive |

## 🔒 Strongly Recommended (adopting all)

| Tech | Our use |
|---|---|
| **Circle Wallets** | Programmable wallets for every agent (Kimchi / Dual-Quote / Meta / Executor). No raw keys. |
| **x402 facilitator** | Producers expose signals as **HTTP 402-paywalled endpoints**. Consumers pay via x402 → USDC on Arc. |

## 🧩 Stretch (Originality boosters)

| Tech | Our use | Difficulty |
|---|---|---|
| **circle-titanoboa-sdk** | Python-native Vyper contract for Signal Registry (matches our Python backbone) | Medium |
| **Vyper-agentic-payments** | Reference impl for agent payment flows | Low (copy patterns) |
| **ERC-8004-vyper** | Agent identity + reputation on-chain (producer reputation by signal P&L) | Medium-High |
| **AIsa digital resources** | Consumers buy from AIsa APIs in demo to prove interop | Low |

---

## Revised Architecture (x402-centric)

```
┌─────────── Producer Agents (Python) ────────────┐
│  Kimchi Agent        Dual-Quote Agent            │
│  (Circle Wallet A)   (Circle Wallet B)           │
└──────┬──────────────────────────┬────────────────┘
       │ expose x402 endpoint     │
       │ GET /signal/kimchi/DOGE  │ ← HTTP 402 if unpaid
       │ GET /signal/dq/SOL       │
       ▼                          ▼
┌──────────────────────────────────────────────────┐
│  x402 Facilitator (Circle)                       │
│  verifies payment header, settles on Arc         │
└─────────────────────┬────────────────────────────┘
                      │ USDC transfer on Arc
                      ▼
┌──────────────────────────────────────────────────┐
│  Arc L1 Testnet (settlement)                     │
│  [optional: ERC-8004 identity + reputation]      │
│  [optional: Vyper Signal Registry via Titanoboa] │
└──────────────────────────────────────────────────┘
                      ▲
                      │ nanopayment per signal fetch
┌─────────────────────┴────────────────────────────┐
│  Consumer Agents                                 │
│  Meta Agent (Gemini, Circle Wallet C)            │
│    - subscribes → Gemini regime classify         │
│    - republishes premium @$0.01 via own x402     │
│  Executor Agent (Circle Wallet D)                │
│    - consumes meta+raw, paper-trades             │
└──────────────────────────────────────────────────┘
```

---

## Prize alignment (updated)

| Target | Prize |
|---|---|
| **Online 1st** (primary goal) | $2,500 USDC |
| Online 2nd | $1,500 USDC |
| Product Feedback Incentive (easy win alongside) | $500 USDC |

> Note: Earlier info about "$40k GCP credits / Google DeepMind challenge" does not appear in the official Circle-sponsor info. Treat as unconfirmed. Gemini integration is still useful for **Application of Technology** axis regardless.

---

## Why this reshuffles priorities

**Before** we planned:
- Roll our own HTTP server + raw Arc RPC calls
- Meta-agent via Gemini as main $40k hook
- Simple JSON signal payloads

**After** (with this new info):
- **x402 paywalled endpoints** = the native pattern judges expect
- **Circle Wallets** = removes the "you built a toy wallet" criticism
- Gemini still useful but no longer the main multiplier — **Vyper/Titanoboa + ERC-8004** are the real Originality unlocks
- **AIsa digital resources** can be woven into demo for "realistic interop"

---

## Next actions (blocks team research agent prompts)

The Circle/Arc research agent now has a sharper brief:
1. Arc testnet setup (faucet, RPC, explorer URL)
2. x402 facilitator: how to integrate client-side + server-side
3. Circle Wallets API: creating programmable wallets for agents
4. circle-titanoboa-sdk: setup + hello-world Vyper contract
5. AIsa digital resources: example endpoints we could consume in demo
