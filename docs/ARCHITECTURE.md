# Architecture — AlphaLoop (formerly "Signal Mesh on Arc")

## Design principles

1. **Reuse, don't rewrite.** v1.1 (`spread_calc`, `signal`) and v1.3 (`capital_allocator_v12`, `live_engine_v2`) signal-generation code is imported verbatim; only the execution side is replaced with a signal-publish call.
2. **Language per strength.** Python for trading / numerical code (reuse). TypeScript for Arc / web3 (SDK ecosystem).
3. **Real onchain.** Every signal consumption = one real Arc testnet USDC transfer. No simulation, no JSON ledger cop-out.
4. **Variable-priced signals.** Per-action pricing $0.0005 – $0.010 (60/30/10 low/mid/high-confidence tier), sampled from the signal-quality distribution the executor's `pricing_policy.choose_price` emits. No flat tier constants.

---

## Components

### 1. Kimchi Signal Producer (Python)
- Input: Upbit WebSocket (KRW) + Binance WebSocket (USDT)
- Logic: reuses `v1_kimchi_premium/src/strategy/spread_calc.py` and `signal.py`
- Output: when KRW↔USDT premium crosses threshold → publish signal to bridge
- Read-only: never places real orders

### 2. Dual-Quote Signal Producer (Python)
- Input: Binance COINUSDT + COINUSDC orderbook WS
- Logic: reuses `v2_dual_quote_arb/src/capital_allocator_v12.py` entry logic
- Output: when USDT↔USDC spread > threshold → publish signal
- Read-only

### 3. Arc Bridge (Node.js / TypeScript)
- HTTP endpoint `/signals/publish` (from producers)
- HTTP endpoint `/signals/consume` (from consumers)
- On consumption: constructs USDC transfer tx on Arc testnet, signs with consumer wallet, broadcasts via Arc RPC
- Exposes tx hashes for the demo UI
- Uses Circle Nanopayments if a high-level SDK is available; otherwise raw Arc RPC + USDC contract call

### 4. Meta Agent (Python + Gemini)
- Subscribes to both producers' raw signals
- Feeds recent window into Gemini: "classify market regime, explain why this signal is / isn't actionable"
- Republishes as a *premium signal* tier at $0.01 with the NL justification attached
- This is the Google DeepMind bonus-track hook

### 5. Executor Agent (Python, demo-only)
- Buys raw signals, runs a tiny paper-trading simulator
- Proof-of-concept that the signals are actually usable, not just published
- Drives 50+ consumption events during the demo

---

## Signal schema (shared)

```json
{
  "signal_id": "uuid",
  "producer": "kimchi" | "dual_quote" | "meta",
  "tier": "raw" | "premium",
  "price_usdc": 0.002,
  "pair": "DOGE",
  "side": "long" | "short",
  "spread_bps": 17.3,
  "timestamp": 1713657600,
  "justification": "optional, Gemini-generated for premium tier",
  "expires_at": 1713657605
}
```

---

## Onchain tx flow (per signal consumption)

```
Consumer Agent                Arc Bridge                Arc L1 Testnet
     │                             │                          │
     │ POST /consume (signal_id)   │                          │
     ├────────────────────────────▶│                          │
     │                             │ build USDC transfer tx    │
     │                             │ sign w/ consumer wallet   │
     │                             ├─────────────────────────▶│
     │                             │                          │
     │                             │ wait for confirmation     │
     │                             │◀─────────────────────────┤
     │  signal payload + tx_hash   │                          │
     │◀────────────────────────────┤                          │
```

---

## Open questions (to resolve via team research)

- **Q1 (Team 1)**: Does Circle publish a high-level Nanopayments SDK, or do we call USDC contract directly?
- **Q1a**: Arc testnet RPC endpoint, chain ID, faucet URL
- **Q1b**: USDC testnet contract address on Arc
- **Q2 (Team 2)**: Which exact files from v1.1 / v1.3 can be imported as-is vs need minor adaptation?
- **Q3 (Team 3)**: Gemini free-tier rate limits — can we run 50 calls in 2 minutes?
- **Q3a**: Google AI Studio vs Vertex AI — which scores better for the $40k track?

---

## Judges (Giants' Shoulders review)

After each phase, we run parallel 3-way critique:
- **Jeremy Allaire** — payments-infra correctness, alignment with Circle's Nanopayments vision
- **Andrej Karpathy** — is the agent architecture principled, or is LLM just decoration?
- **Balaji Srinivasan** — does the M2M economy story hold up? Would anyone pay?

Each produces a 1-page memo with strengths / risks / one concrete demand.
