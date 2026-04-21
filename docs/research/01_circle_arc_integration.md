# Circle/Arc/x402 Integration Brief (Team Member 1 Output)

> Produced by research agent, 2026-04-21

## 1. Arc Testnet Basics

| Item | Value |
|---|---|
| Public RPC | `https://rpc.testnet.arc.network` |
| Alchemy RPC (paid, better for demo) | `https://arc-testnet.g.alchemy.com/v2/<API_KEY>` |
| **Chain ID** | `5042002` (`0x4cef52`) |
| **Native gas token** | **USDC** (not ETH) — fees in dollars |
| Block explorer | `https://testnet.arcscan.app` |
| Faucet | `https://faucet.circle.com` or `https://console.circle.com/faucet` (20 USDC / 2h / addr) |
| Developer Account | `https://console.circle.com` |

## 2. USDC on Arc Testnet

- **Contract**: `0x3600000000000000000000000000000000000000`
- **★ DUAL DECIMAL TRAP**:
  - Native USDC uses **18 decimals**
  - ERC-20 interface exposes **6 decimals**
  - Mixing = 10^12× size error. Write helper + unit-test first.

Python (web3.py):
```python
from web3 import Web3
w3 = Web3(Web3.HTTPProvider("https://rpc.testnet.arc.network"))
USDC = w3.to_checksum_address("0x3600000000000000000000000000000000000000")
c = w3.eth.contract(address=USDC, abi=ERC20_ABI)
tx = c.functions.transfer(to, int(0.01 * 10**6)).build_transaction({
    "from": acct.address, "chainId": 5042002, ...})
```

Node.js (viem):
```ts
const arcTestnet = defineChain({
  id: 5042002, name: 'Arc Testnet',
  nativeCurrency: { symbol:'USDC', decimals:18 },
  rpcUrls:{ default:{ http:['https://rpc.testnet.arc.network'] } }
})
await client.writeContract({
  address:'0x3600...0000', abi, functionName:'transfer',
  args:[recipient, parseUnits('0.01', 6)]
})
```

## 3. Circle Nanopayments (★ core)

- **NOT** direct USDC transfer. Off-chain ledger + batched on-chain settlement on Circle Gateway.
- Uses **x402 standard** + **EIP-3009 `transferWithAuthorization`**.
- Agent signs EIP-3009 → Circle aggregates + settles periodically → sub-cent ($0.000001) transfers with **zero per-tx gas to agent**.
- **Docs**: `https://developers.circle.com/gateway/nanopayments`
- **Sample repo**: `github.com/circlefin/arc-nanopayments`
- **No dedicated "nanopay SDK"** — use Circle Developer SDK + sign EIP-3009 via `signTypedData`, POST to `/v1/gateway/x402/settle`.

## 4. x402 Facilitator (★ adopt)

- **Spec**: HTTP 402 Payment Required + machine-readable payment terms + `X-Payment` header w/ signed EIP-3009 auth.
- **Facilitator URL**: `https://x402.org/facilitator` (Coinbase default)
- **Circle's facilitator**: via Gateway endpoints on `api.circle.com`
- **Repo**: `https://github.com/coinbase/x402`

Server middleware:
- Node: `npm i x402-express`
- Python: `pip install x402`

Server example (Express):
```ts
import { paymentMiddleware } from 'x402-express'
app.use(paymentMiddleware(recipientAddress,
  { 'GET /signal': { price: '$0.01', network: 'arc-testnet' } },
  { url: 'https://x402.org/facilitator' }))
```

Client: `@x402/axios` or `@x402/fetch` auto-handles 402 → sign → retry with `X-Payment` header.

## 5. Circle Wallets

- API: `POST /v1/w3s/developer/wallets`
- Auth: API key + **Entity Secret** (AES-encrypted, rotated per call)
- MPC-custodied; Circle holds key shards
- Node SDK: `@circle-developer/sdk`
- Python SDK: `circle-developer-controlled-wallets`
- Programmatic faucet: `POST api.circle.com/v1/faucet/drips { address, blockchain:"ARC-TESTNET", usdc:true }`

## 6. Circle Developer Console (★ required for submission video)

- URL: `https://console.circle.com`
- **YES — Arc testnet USDC transfer from UI supported**
- Flow: Wallets → pick wallet → "Send" or "Contract Execution" → network `ARC-TESTNET` → `transfer(recipient, amount_6dec)` → submit → tx hash opens on `testnet.arcscan.app`
- **This satisfies the hackathon "transaction flow" video requirement.**

## 7. AIsa

- Unified resource API (LLMs, search, SaaS skills) accepting x402
- Processed >22M x402 micropayments
- Docs: `https://aisa.one/docs`
- GitHub: `https://github.com/AIsa-team`
- OpenAI-compatible base URL, $2 free credit
- **Demo idea**: consumer agent receives our signal → enriches via AIsa x402 → resells. Shows 2-hop nanopayment loop.

## 8. Vyper / Titanoboa stretch (⚠️ unconfirmed)

- **`circle-titanoboa-sdk`** — **Could not locate in github.com/circlefin**. Circle may mean community tutorials. Do NOT promise in pitch until verified on Discord.
- **`ERC-8004-vyper`** — Not visible; canonical Solidity only at `github.com/erc-8004/erc-8004-contracts`
- **Realistic?** Writing Vyper from scratch: NO. Register agents via existing Solidity ERC-8004: YES (~2h stretch).

## ⚠️ Red flags / blockers

1. **Dev Console login required before recording demo** — verify Arc testnet USDC flow manually first
2. **`arc-nanopayments` sample not directly fetched** — clone + verify chain 5042002 + SDK versions
3. **USDC dual-decimal trap** (see §2)
4. **Public RPC may rate-limit** under demo load → Alchemy fallback
5. **`circle-titanoboa-sdk` unconfirmed** — don't commit in pitch
6. **x402 + Arc**: most `x402-express` samples hardcode `base-sepolia`. Verify `arc-testnet` is accepted; if not, point facilitator URL at Circle Gateway
7. **Entity Secret rotation**: per-call encrypted with rotating public key. Use official SDK — don't roll REST

## Quickstart

```bash
cd C:\Users\user\hackerton\arc
# Node
npm init -y && npm i x402-express @x402/axios @circle-developer/sdk viem dotenv
# Python
python -m venv .venv && .venv\Scripts\activate
pip install web3 x402 eth-account requests python-dotenv google-genai
# Sample
git clone https://github.com/circlefin/arc-nanopayments samples/nano
# RPC smoke
curl -X POST https://rpc.testnet.arc.network -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_chainId\",\"params\":[],\"id\":1}"
# expect {"result":"0x4cef52",...}
```

## Sources

- Circle Nanopayments launch blog
- Circle Wallets + x402 tutorial
- x402 repo: github.com/coinbase/x402
- Arc testnet announcement
- Arc contracts reference: docs.arc.network
- ChainList: chainlist.org/chain/5042002
- console.circle.com, faucet.circle.com
- aisa.one + github.com/AIsa-team
- ERC-8004 contracts: github.com/erc-8004/erc-8004-contracts
