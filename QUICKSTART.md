# Signal Mesh on Arc — Quickstart

## 1. 🧑 User manual steps (prerequisites)

These must be done by the human — accounts and keys.

### 1.1 Circle Developer Account (~5 min)
1. Go to https://console.circle.com
2. Sign up **with the same email used for lablab.ai hackathon registration**
3. From the dashboard, navigate to: **Wallets → Wallet Sets → Create Wallet Set**
4. Inside the Wallet Set, create **4 developer-controlled wallets** named:
   - `producer_kimchi`
   - `producer_dual_quote`
   - `meta_agent`
   - `executor_agent`
5. For each wallet, note the **Arc testnet address** (0x…)
6. Go to **Faucet** (within console) and drip **20 USDC per wallet** (Arc testnet).
7. Copy your **API Key** and **Entity Secret** from the account settings.

### 1.2 Google AI Studio API Key (~2 min)
1. Go to https://aistudio.google.com
2. Click "Get API key" → create new
3. Save the key.

### 1.3 `.env` file
Create `C:\Users\user\hackerton\arc\.env`:
```ini
# Circle
CIRCLE_API_KEY=xxx
CIRCLE_ENTITY_SECRET=xxx
CIRCLE_WALLET_SET_ID=xxx

# Wallet addresses (from step 1.1)
WALLET_KIMCHI=0x...
WALLET_DUAL_QUOTE=0x...
WALLET_META=0x...
WALLET_EXECUTOR=0x...

# Gemini
GOOGLE_AI_API_KEY=xxx

# Bridge
ARC_BRIDGE_URL=http://localhost:3000
PORT=3000
FACILITATOR_URL=https://x402.org/facilitator
ARC_RPC_URL=https://rpc.testnet.arc.network
ARC_CHAIN_ID=5042002

# x402 paywall (leave disabled until the facilitator accepts arc-testnet)
X402_ENABLED=0
X402_NETWORK=arc-testnet
PRODUCER_WALLET_ADDRESS=0x...   # meta_agent wallet (receives x402 fees)

# Executor on-chain settlement (optional — off = paper only)
EXECUTOR_PRIVATE_KEY=0x...       # exported from Circle Dev Console, or external EOA
TREASURY_ADDRESS=0x...           # where settlement USDC lands (producer_dual_quote wallet)
USDC_ADDRESS=0x3600000000000000000000000000000000000000
```

## 2. 🖥️ Install

```bash
# From C:\Users\user\hackerton\arc

# Python (producers + meta agent + GBM)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Node (bridge)
cd bridge
npm install
cd ..
```

## 3. 🚀 Run the demo stack

### Option A — one-shot driver (recommended)

```bash
# T1
cd bridge && npm run dev

# T2 (new terminal)
.venv\Scripts\activate
# optional: train the GBM once (2–4 min on the full 87-pair dataset)
python -m ml.regime_gbm
# run the full mesh for 2 minutes
python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 120
```

### Option B — manual four-terminal

| Term | Command |
|---|---|
| 1 | `cd bridge && npm run dev` |
| 2 | `python -m producers.dual_quote_agent.main --symbol DOGE --date 20260419 --speed 30` |
| 3 | `python -m consumers.meta_agent.main --interval 3` |
| 4 | `python -m consumers.executor_agent.main --interval 3 --settle-every 1 --settle-amount 0.01` |

### Health / inspection
```bash
curl http://localhost:3000/health
curl http://localhost:3000/signals/latest
curl http://localhost:3000/signals/premium
curl http://localhost:3000/tx/recent
```

## 3.1 Capital Allocator warm-up (RL centerpiece — see SUBMISSION §12)

The Allocator is the hackathon's headline RL agent (tabular Q-learning over `9 states × 7 actions`, reward aggregated per 8h Binance funding cycle). It needs a one-time pretrain pass before the demo, then runs alongside the rest of the stack.

```bash
# 1. pretrain the allocator Q-table (once, ~30-60s)
#    Reads data/funding/*_90d.parquet (5 symbols × 271 ticks = 1355 real 8h cycles),
#    writes consumers/capital_allocator/allocator_q.json + calibrated mu/sigma.
python scripts/pretrain_allocator_q.py

# 2. start the online allocator alongside producers + meta + executor
#    --allocator-tick-seconds 30  == DEMO cadence (prod = 28800 = 8h)
#    --v3-entry-offset-sec 0      == demo offset (prod = 180, see SUBMISSION §12 / design §5.6)
python -m consumers.capital_allocator.main \
    --allocator-tick-seconds 30 \
    --v3-entry-offset-sec 0

# 3. verify in browser: http://localhost:5173
#    → "Capital Allocator" section populates within one tick (≤30s in demo)
```

**Cadence vs v3 offset — production relationship.** At prod cadence (28800s / 8h), v3 OPEN execution is deferred **+180s** past each allocator tick to avoid the funding-print crowding window (design doc §5.6, Griffin resolution — "execution edge, not alpha edge"). In demo mode (30s tick), the offset scales to ~0s because +3min is meaningless inside a 30s decision window and the crowding mechanic only exists around the actual 00:00 / 08:00 / 16:00 UTC prints. The dashboard `AllocatorCard` surfaces both values so the distinction is visible on screen.

## 4. 🎥 Demo video flow (for submission)

1. **Terminal recording**: run `python -m demo.run_demo` → watch the live `t+XXs raw=… premium=… onchain_tx=…` ticker → end on the summary block with tx hash URLs
2. **Circle Developer Console**: log in → execute one USDC `transfer` via Contract Execution UI on Arc testnet → show tx hash (this satisfies the Circle Console requirement)
3. **Arc Block Explorer** (`testnet.arcscan.app`): open one of the hashes from the summary → show confirmation + amount
4. **(Optional)** React dashboard: live signal stream + settled-tx list

## 5. 🗺️ What's built vs TODO

| Component | Status |
|---|---|
| `producers/shared/signal.py` — unified schema | ✅ |
| `producers/kimchi_agent/` — pure signal modules | ✅ (main.py TODO: needs KRW+FX feed) |
| `producers/dual_quote_agent/main.py` — parquet replay + allocator | ✅ |
| `bridge/src/index.ts` — HTTP store + x402 paywall toggle + `/tx/report` | ✅ |
| `bridge/src/arc.ts` — viem Arc chain + USDC helpers | ✅ |
| `consumers/meta_agent/` — Gemini 2.5 Flash + GBM regime blend | ✅ |
| `consumers/executor_agent/` — premium consumer + real Arc USDC settle | ✅ |
| `ml/regime_gbm.py` — sklearn GBM trained on v1.3 parquet | ✅ |
| `demo/run_demo.py` — one-shot orchestrator | ✅ |
| Frontend dashboard (React + Vite) | 🔧 TODO |
| Kimchi live main.py (needs KRW+FX feed) | 🔧 TODO |
