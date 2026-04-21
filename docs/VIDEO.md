# Video script — Signal Mesh on Arc (≤ 3 minutes)

Two videos to upload:
1. **Main pitch + demo** (3 min)
2. **Transaction flow verification** (≤ 60 sec, Circle Developer Console + Arc Explorer)

Both as MP4. Scrub secrets before recording.

---

## Video 1 — Pitch + live demo (target 3:00)

### 0:00–0:30  **The wedge — Arc vs Base, side by side** (split-screen, no narration first 3s)

Cold open: split-screen, both halves running the *same* signal-publish call.
- **Left:** Base mainnet — terminal shows `tx fee: $0.012 (ETH)` then `wallet ETH balance: 0.0008` highlighted in red. Caption: "agent paid USDC. gas paid in ETH. who refills the ETH?"
- **Right:** Arc testnet — terminal shows `tx fee: $0.0003 (USDC)` and `wallet USDC balance: $4.91 → $4.9097`. Caption: "same call. gas in USDC. agent self-balances."

Voiceover starts at 0:03:
> "Same A2A call, two chains. Left: gas in ETH, signal in USDC — a human has to keep refilling that ETH wallet. Right: gas in USDC, signal in USDC. The agent closes its own books. That is the wedge. Everything we built is downstream of it."

End the shot on the cover image (`Signal Mesh on Arc`) for ~2 seconds.

### 0:30–0:50  Problem (slide 3 — quick)
- Per-signal value is $0.002–$0.01. On Base/Polygon/Solana, gas is a large fraction of that.
- Worse: agent earns USDC, pays gas in ETH/MATIC/SOL — **two-unit accounting**, cannot self-balance.
- Every existing "agent economy" demo has a human topping up the gas wallet. That's the hidden human.

### 0:50–1:15  Why Arc (slide 4)
- USDC *is* the native gas token on Arc.
- Signal priced in USDC, paid in USDC, gas in USDC. Closed loop, single unit of account.
- An agent earning downstream premiums can keep paying upstream producers forever.

### 1:15–2:00  **Live demo — marketplace** (screen-record dashboard, 45s)
- Terminal left: `python demo/run_demo.py --with-kimchi --target-tx 60`
- Browser right: `https://signal-mesh.vercel.app`
- Narrate as counters tick up:
  - "raw signals stream from three producers — the dual-quote feed is **a replay of my live v1.3 production arb bot's 1-second tape from April 19**, v3 funding is real Binance fapi funding data, not synthetic"
  - "meta-agent is Gemini 2.5 Flash arbitrating, weighted by each producer's hit-rate"
  - "every premium decision sets the on-chain price — watch the settlement tx land"
- Click one tx link → `testnet.arcscan.app/tx/0x…` opens confirmed tx.
- Show producer reliability bars updating as positions close.

### 2:00–2:30  **Allocator RL beat** (30s — the actual RL claim)
Three sub-shots, cut tight. VO verbatim (~60 words):
> "The pricing Q-table you just saw is an operational fee-recovery tool. The Allocator is the RL agent. It's a tabular Q-learner deciding which of three arb strategies owns capital for the next eight hours — Binance's funding cadence. Nine regime states, seven allocation actions, pretrained on three months of real Binance funding, one day of live production tape, and clearly-labeled synthetic kimchi. Watch what it learned."

- **2:00–2:05 (5s)** — Cut to dashboard `AllocatorCard`. Narrate: "this is the Allocator deciding which strategy owns capital for the next 8 hours."
- **2:05–2:17 (12s)** — Cut to `PolicyHeatmap`. Narrate: "9 regime states × 7 allocation actions, pretrained on 3 months of Binance funding + 24 hours of real production 1s bars + synthetic kimchi. Each cell shows what the policy learned: hot vol + hot funding → ALL_V3; cold everywhere → DIVERSIFY."
- **2:17–2:30 (13s)** — Flip a regime manually via ENV override (pre-staged terminal command). Cut back to heatmap: "policy responds to regime shift, not to signal volume" — show the allocation change within 2 ticks. Badge still reads "demo cadence 30s / prod 8h."

### 2:30–2:50  Originality (slide 7)
- Variable on-chain price encodes signal quality (not a receipt constant).
- Outcome feedback retroactively re-prices future signals from the same producer.
- The Allocator sits above all of that: a learned meta-policy, not a threshold.
- That is the loop. It's a real market, not a cron job.

### 2:50–3:00  CTA
> "Repo, live dashboard, product feedback — all linked in the submission.
> Signal Mesh on Arc. Thanks for judging."

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
> The full demo runs ~60 of these through the agent pipeline."

---

## Pre-record checklist

- [ ] `.env` has no secrets visible on screen during recording
- [ ] Bridge running with `X402_ENABLED=1`
- [ ] Executor running with `--nanopay`
- [ ] Dashboard already loaded and warmed up (2–3 tx already landed)
- [ ] Terminal font size large enough to read
- [ ] Arc Explorer tab pre-loaded
- [ ] Screen recorder at 30fps minimum, audio level tested
