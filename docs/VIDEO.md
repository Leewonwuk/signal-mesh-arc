# Video script — AlphaLoop (≤ 3 minutes)

Two videos to upload:
1. **Main pitch + demo** (3 min)
2. **Transaction flow verification** (≤ 60 sec, Circle Developer Console + Arc Explorer)

Both as MP4. Scrub secrets before recording.

---

## Video 1 — Pitch + live demo (target 3:00)

### 0:00–0:30  **The wedge — Arc vs Base, side by side** (split-screen + title card)

0:00–0:02 **Title card, on-screen text only** (no narration yet):
> **"Every other agent economy has a human refilling the gas wallet. On Arc, there isn't one."**

0:02–0:30 Cold open split-screen, both halves referencing the *same* signal-publish call:
- **Left:** Base mainnet — screenshot of Etherscan gas tracker showing median ~$0.012 USD per transfer with the caption "gas paid in ETH · agent earns USDC · who refills the ETH?" (Screenshot, not live — Base mainnet tx would consume real ETH; we avoid staging fake receipts.)
- **Right:** Arc testnet — live `curl https://testnet.arcscan.app/tx/0x…` showing `fee: ~0.007 USDC` on a real settlement tx from `docs/evidence/batch_tx_hashes.txt`. Caption: "gas in USDC. agent self-balances."

Voiceover starts at 0:02:
> "Same A2A call, two economies. Left: gas in ETH, signal in USDC — a human has to keep refilling that ETH wallet. Right: gas in USDC, signal in USDC. The agent closes its own books. That is the wedge. Everything we built is downstream of it."

End the shot on the cover image (`AlphaLoop`) for ~2 seconds.

### 0:30–0:50  Problem (slide 3 — quick)
- Per-signal value is $0.002–$0.01. On Base/Polygon/Solana, gas is a large fraction of that.
- Worse: agent earns USDC, pays gas in ETH/MATIC/SOL — **two-unit accounting**, cannot self-balance.
- Every existing "agent economy" demo has a human topping up the gas wallet. That's the hidden human.

### 0:50–1:15  Why Arc (slide 4)
- USDC *is* the native gas token on Arc.
- Signal priced in USDC, paid in USDC, gas in USDC. Closed loop, single unit of account.
- An agent earning downstream premiums can keep paying upstream producers forever.

### 1:15–2:00  **Live demo — marketplace** (screen-record dashboard, 45s)

Two processes drive the screen:
- **Terminal left (marketplace dynamics)**: `python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 600 --speed 100 --threshold 0.0005 --fee-rate 0` — producers + meta + executor (paper) + allocator. Drives raw/premium counters, Q-learning outcomes, heatmap updates.
- **Terminal right (on-chain evidence)**: `node scripts/circle_batch_settle.js --count 150 --rate 3` — Circle Developer API fires 150 **variably-priced** USDC transfers ($0.0005–$0.010) through the 4 SCA wallets on Arc testnet; each `OK` event POSTs to bridge `/tx/report` so the dashboard's Settlement tx card fills in real time.

Why two drivers: Arc testnet raw-EOA mempool hit "txpool is full" during build; Circle-managed signing routes around it. We show both — the executor codepath (`--nanopay` EIP-3009) validated in `consumers/executor_agent/main.py`, and the Circle Developer API batch that ships the 150 variably-priced tx. Same marketplace, two production-grade paths.

- Browser right: local dashboard at `http://localhost:5173` (live data via local bridge). The public deploy at `https://signal-mesh.vercel.app` shows the same UI but is a static scaffold — use localhost for recording.
- Narrate as counters tick up:
  - "raw signals stream from three producers — the dual-quote feed is **a replay of my live v1.3 production arb bot's 1-second tape from April 19**, v3 funding is real Binance fapi funding data, clearly-labeled synthetic kimchi"
  - "meta-agent is Gemini 2.5 Flash arbitrating, weighted by each producer's hit-rate"
  - "150 on-chain USDC settlements land via Circle's Developer API — each variably priced by signal quality, real block on arcscan"
- Click one tx link → `testnet.arcscan.app/tx/0x…` opens confirmed tx.
- Show producer reliability bars updating as positions close.

### 2:00–2:30  **Allocator RL beat — lead with the receipt** (30s)

Garry Tan fix: put the walk-forward leaderboard on screen. VO verbatim (~55 words):
> "This is a learned allocator picking which strategy owns capital. We ran it out-of-sample against Ridge, LightGBM, and a one-line if-statement. It ties the empirical optimum — p equals 0.49 — and beats every other learner. The convergence *is* the rigor signal. If it had diverged, that would have been the bug."

- **2:00–2:10 (10s)** — Full-screen render of the §11.b leaderboard table (from `docs/SUBMISSION.md:188-195`). `TrainedQ_walkforward` row highlighted. p-values visible.
- **2:10–2:22 (12s)** — Cut to `PolicyHeatmap` card. Narrate: "9 regime states × 7 allocation actions. Empty ALL_V3 cells are expected — 90% of the 90-day window was cold-funding. A heatmap that enthusiastically picked ALL_V3 would be the red flag."
- **2:22–2:30 (8s)** — Flip persona to Coinbase in `FeeExplorer`. Narrate: "persona demotion counter ticks — the bridge gates premium lanes by persona in real time." Badge still reads "demo cadence 30s / prod 8h."

### 2:30–2:50  Originality (slide 7)
- Variable on-chain price encodes signal quality (not a receipt constant).
- Outcome feedback retroactively re-prices future signals from the same producer.
- The Allocator sits above all of that: a learned meta-policy, not a threshold.
- That is the loop. It's a real market, not a cron job.

### 2:50–3:00  CTA
> "Repo, live dashboard, product feedback — all linked in the submission.
> No human in the loop. That's the unlock.
> **AlphaLoop.**"

---

## Video 2 — Transaction flow verification (≤ 60 sec)

Purpose: satisfy the explicit submission requirement that **one tx is executed via Circle Developer Console and verified on Arc Block Explorer**.

### 0:00–0:15  Console
- Open Circle Developer Console.
- Show Arc testnet wallet balance.
- Click "Send USDC" → paste treasury address → amount `0.01` → submit.

### 0:15–0:30  Pending
- Console shows pending tx hash. Copy hash.

### 0:30–0:55  Arc Block Explorer
- Open `testnet.arcscan.app`, paste the hash.
- Show: ✅ Confirmed · block number · USDC token transfer event.

### 0:55–1:00  End card
> "One tx via Circle Console. Verified on Arc Explorer.
> The full demo runs 150 variably-priced settlements like this through the AlphaLoop pipeline, from half-a-tenth of a cent to the one-cent cap."

---

## Pre-record checklist

- [ ] `.env` has no secrets visible on screen during recording (token, key cols scrubbed)
- [ ] Bridge running on :3000 — `cd bridge && npm run dev`
- [ ] Dashboard running on :5173 — `cd dashboard && npm run dev`
- [ ] Demo driver running (paper mode) — `python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 900 --speed 100 --threshold 0.0005 --fee-rate 0`
- [ ] Circle batch armed — `node scripts/circle_batch_settle.js --count 150 --rate 3` (fire when recording begins 1:15 cue)
- [ ] Persona set via curl BEFORE opening dashboard (FeeExplorer skips initial POST now, but setting first makes first paint clean):
  ```bash
  curl -X POST http://localhost:3000/policy/persona -H 'Content-Type: application/json' \
    --data-binary '{"exchangeId":"bybit","label":"Bybit - VIP 0 + USDC 50% off","feeRoundTrip":0.0015,"thresholdRate":0.0017,"supportsDualQuoteArb":true}'
  ```
- [ ] Allocator pre-warmed — let it publish ≥3 ticks before recording so heatmap cells populate
- [ ] Dashboard visible viewport includes Capital Allocator card (Allocator section is now above FeeExplorer for first-fold hero placement)
- [ ] Arc Explorer tab pre-loaded on first batch tx hash (see `docs/evidence/batch_tx_hashes.txt`)
- [ ] Screen recorder at 30fps minimum, 1080p, audio level tested
- [ ] Terminal font size ≥ 14pt
