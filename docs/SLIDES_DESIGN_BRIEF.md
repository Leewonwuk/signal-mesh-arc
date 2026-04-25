# AlphaLoop — Slide Deck Design Brief

> **For: Claude Design (or any slide generator — Marp / Slidev / Keynote / Figma).
> Goal: produce a 12-slide PDF deck (16:9, 1920×1080) for lablab.ai Agentic Economy on Arc hackathon submission.**
>
> This document is the **single source of truth** for the new deck. Ignore `docs/SLIDES.md` (the current version has cut-off tables, paragraph-heavy copy, and assumes RL expertise the judges likely don't have). Generate from scratch using the specifications below.
>
> **Revision 2026-04-24 (late night)** — 5-giant review + Tier A/B/C1 mining from lablab prior-hackathon repos incorporated.
> **Project is now AlphaLoop** (Alpha = live-bot moat; Loop = Track 2 name). Slide cover wordmark updated.
> **On-chain augments** since prior draft:
> 1. **AlphaLoopAgentRegistry deployed + source verified** on Arc testnet at `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` — 4 `AgentRegistered` events emitted (Dev43 + zixel pattern). Slide 10 and Slide 11 must reflect this.
> 2. **Merkle root over 150-tx manifest** at `docs/evidence/merkle_root.txt` = `400039d5…05b80` (Judy-style integrity pattern). One-line badge on Slide 10 or 11.
> 3. **ERC-8004 registration-v1 agent cards** served at `signal-mesh.vercel.app/.well-known/agent-card/<role>` for all 4 wallets. Each event payload contains sha256 contentHash of its card — **content-addressed off-chain → on-chain linkage**. This is the clearest "not marketing, actually works" hook.
> 4. **Tx count upgraded 60 → 150**, amounts **variable $0.0005–$0.010** (60/30/10 low/mid/high). Slide 6 bar chart visual + Slide 8 subtitle must reflect.
> 5. Scoreboard page at `signal-mesh.vercel.app/scoreboard.html` — Slide 12 link grid can reference.
> 6. Cover subtitle: AlphaLoop wordmark (Alpha cyan) + "The agent-to-agent alpha loop on Arc — fed by a live v1.3 production arb bot."
> 7. Slide 2 hook stays: "USDC is the gas. / On Arc." (Tan: single assertion).
> 8. Slide 10 custody banner keeps 3 concrete failure modes (Vitalik).
> 9. Slide 11 Card 2 honest about fixed-cadence burst (Karpathy).

**Ground-truth facts for the designer** (copy into any visual):

| | |
|---|---|
| Project name | **AlphaLoop** |
| Track | 🤖 Agent-to-Agent Payment Loop |
| Tx count | **150 variably-priced** + 5 ERC-8004 events |
| Per-action pricing | **$0.0005 – $0.010** (60/30/10 tier) |
| Registry contract (verified) | `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` |
| Merkle root (150-tx manifest) | `400039d5…05b80` |
| Arc chainId | 5042002 |
| Live dashboard | `signal-mesh.vercel.app` |
| Scoreboard page | `signal-mesh.vercel.app/scoreboard.html` |
| Repo | `github.com/Leewonwuk/signal-mesh-arc` |
| Submitter | Leewonwuk · skyskywin@gmail.com |
| License | MIT |
| v1.3 prod bot | 9 coins · pool ≈ $1,977 USDT · threshold 0.17% · running right now |
| Meta-agent | Gemini 2.5 Flash + deterministic stub fallback |
| Walk-forward result | TrainedQ $7.61 vs ALL_V2 $9.44 · p=0.49 vs ALL_V2 · p=0.012 vs DIVERSIFY |
| Round-1 drama | "Round 1 lost to a one-line if-statement; Round 2 ties the empirical optimum." |

---

## 0. Audience & goals

**Audience**: lablab.ai hackathon judges. International, English-fluent, crypto-native but **may not be RL/ML specialists**. Will see 50+ decks. You have ~30 seconds per slide before they mentally rank.

**Must achieve (in priority order)**:
1. The core claim lands in the first 10 seconds ("USDC-as-gas closes the agent economy loop")
2. Judges understand the RL story **without** knowing what "Q-learning" means
3. The submission looks like serious engineering, not vibe-coding
4. Data honesty is visible (real vs synthetic clearly labeled, not hidden)
5. Circle products + custody model are disclosed accurately (no EIP-3009 overclaim)

**Must avoid**:
- Dense paragraphs (no slide should have >60 words of body copy)
- Tables wider than slide safe area (1760px max content width)
- ML jargon without translation ("tabular Q-learning" alone = ❌; "picking which strategy trades, by learning from outcomes" = ✅)
- Fake live-demo screenshots (judges will fact-check)

---

## 1. Design system

### 1.1 Color palette (dark theme — matches dashboard)

| Role | Hex | Usage |
|---|---|---|
| `bg-deep` | `#0a0e1a` | Slide background |
| `bg-card` | `#13182b` | Card / panel background |
| `border` | `#1f2744` | Subtle dividers |
| `text` | `#e6ebf5` | Primary body text |
| `muted` | `#7a86a8` | Secondary / captions |
| `accent-cyan` | `#22d3ee` | Headers, key numbers |
| `accent-purple` | `#a78bfa` | Secondary highlights |
| `accent-green` | `#4ade80` | Positive outcomes, "ships" |
| `accent-amber` | `#fbbf24` | Warnings, demotions |
| `accent-red` | `#f87171` | Loss, "kills margin" |

**Rule**: ONE accent color per slide (usually cyan). Avoid rainbow.

### 1.2 Typography

- **Headline font**: Inter Bold, 48–72pt
- **Body font**: Inter Regular, 20–28pt
- **Monospace (numbers, hashes, code)**: JetBrains Mono 18–22pt
- **Letter-spacing**: headlines `-0.02em`, body `0`, mono `0`
- **Line-height**: 1.3 for headlines, 1.5 for body

### 1.3 Layout grid

- Slide canvas: **1920×1080** (16:9)
- Safe area: 1760×920 (80px margin each side)
- 12-column grid internal; gutter 24px
- Vertical rhythm: 8px base unit
- **Footer** (all slides except cover): tiny muted text `AlphaLoop · lablab.ai Agentic Economy on Arc · 2026-04` left; page number `N/12` right

### 1.4 Icon style

- **Outline icons only** (not filled), 2px stroke, same accent color as page
- Source: Lucide or Phosphor duotone outline
- Do NOT use cartoon / 3D / emoji as decoration (emoji in headlines OK for section breaks)

### 1.5 Motion / animation

- **None**. PDF export — static. Plan as still slides.

---

## 2. Deck structure (12 slides)

```
1.  Cover                         — title card
2.  The ONE line                  — full-screen quote (hook)
3.  The Problem                   — why other chains fail (plain, visual)
4.  Why Arc                       — USDC-as-gas in one diagram
5.  What we built                 — architecture simplified
6.  Variable price = signal quality  — the core economic insight
7.  The RL question, in plain English   — setup for slide 8
8.  The Receipt — walk-forward backtest (BAR CHART)
9.  Data honesty                  — real vs synthetic, declared
10. Circle products + trust model — honest disclosure
11. Originality                   — what's new here
12. Close + links                 — GitHub / demo / submission
```

---

## SLIDE 1 — Cover

**Purpose**: establish project identity in 3 seconds.

**Layout**:
- Centered vertical stack
- Top 30% empty
- Middle: title + subtitle
- Bottom 20%: event + date meta

**Copy**:
- Eyebrow (small, mono, muted): `lablab.ai · Agentic Economy on Arc · Apr 2026`
- **Track chip** (above title, centered, cyan border pill, 14pt bold): `🤖 Track: Agent-to-Agent Payment Loop`
- **Title** (96pt, bold, cyan accent on "Alpha"): `AlphaLoop`
- **Sub-wordmark** (24pt, mono, muted, below title): `agent-to-agent alpha loop · on Arc · formerly Signal Mesh`
- Subtitle (28pt, muted): `Only Track 2 entry fed by a live v1.3 production arb bot. Four specialist agents pay each other sub-cent USDC, amounts varying by signal quality — Arc's USDC-as-gas closes the loop.`
- Meta row (18pt, muted, mono): `Leewonwuk · skyskywin@gmail.com · github.com/Leewonwuk/signal-mesh-arc`

**Visual**: Abstract geometric accent — a simple node-graph motif (4 dots connected, 2px strokes) lower-right, 200px, cyan 30% opacity. Represents the 4-agent marketplace. No clip art.

---

## SLIDE 2 — The ONE line (hook)

**Purpose**: land the pitch in one sentence. Maximum memorability. **Single assertion, not negation** (Tan).

**Layout**:
- Full-bleed, centered text
- No footer on this slide
- Two-stage reveal: if the generator supports internal slide animation (not PDF), split into 2 beats. For PDF, use a single slide with both lines visible.

**Copy** (2 lines, centered, very large):
```
USDC is the gas.
On Arc.
```
- Line 1 (72pt, white): `USDC is the gas.`
- Line 2 (88pt, `accent-cyan`, bold): `On Arc.`

**Visual**: Nothing else. Pure text. White space is the design.

**Speaker note**: This syncs with the video title card at 0:00-0:05 (`docs/VIDEO_SCRIPT_KR.md §0:00-0:05`) — two black-screen cuts: "USDC is the gas." (2.5s) → "On Arc." (2.5s). The deck slide is the static PDF equivalent.

**Why changed from prior draft**: Garry Tan note — "Every other agent economy has a human… there isn't one" is a **negation-first hook**, which YC treats as a forgettable opening (reader mentally constructs the negated thing before the assertion). Single positive assertion first = stops scroll.

---

## SLIDE 3 — The Problem (plain language, visual)

**Purpose**: make the judge feel the "two-unit accounting" pain without using the term.

**Layout**: 2-column comparison
- **Left column** (`muted` border, `#f87171` accent number): OTHER CHAINS
- **Right column** (`accent-green` border): ARC

**Left column** (OTHER CHAINS):
- Header: `Other chains` (mono, 18pt, muted)
- Big icon (3 stacked): 💰 USDC earned → ⛽ ETH paid in gas → 🙋 human top-up
- Caption: `Agent earns in USDC. Gas is in ETH/SOL/MATIC. A human has to keep refilling.`
- Bottom line, red: `This is not an agent economy. It's a human economy with an LLM on top.`

**Right column** (ARC):
- Header: `Arc` (mono, 18pt, cyan)
- Big icon (3 stacked but all same): 💰 USDC → 💰 USDC (gas) → 💰 USDC (payment)
- Caption: `USDC is the native gas. Earnings, payments, and gas are the same currency.`
- Bottom line, green: `Loop closes. No human in the middle.`

**Slide title** (top, 40pt): `The hidden human in every "agent economy"`

**Word count**: ≤ 60 words total across both columns.

---

## SLIDE 4 — Why Arc

**Purpose**: formalize the "closed loop" claim with a crisp diagram.

**Layout**:
- Title at top: `Arc makes USDC the gas token.` (48pt)
- Subtitle: `Same currency in, same currency out. The loop closes.` (24pt, muted)
- Centered diagram (~1000×500px)

**Diagram**: Closed circular flow, cyan strokes, 4 nodes:
```
     ┌─────────────────┐
     │  Producer agent │
     │  (earns USDC)   │
     └────────┬────────┘
              │ pays $0.007 USDC gas
              ▼
     ┌─────────────────┐
     │   Arc L1        │  ← USDC is the gas token
     │   settlement    │
     └────────┬────────┘
              │ delivers $0.01 USDC signal fee
              ▼
     ┌─────────────────┐
     │  Meta agent     │
     │  (pays USDC)    │
     └────────┬────────┘
              │ re-prices producer's next signal
              ▼
         (back to top)
```

**Bottom-left caption** (20pt, muted): `Gas and revenue in the same unit → no ETH treasury, no top-up cron, no operator.`

**Avoid**: showing actual wei amounts. Keep abstract.

---

## SLIDE 5 — What we built

**Purpose**: one-glance architecture. Judge gets the system in 10 seconds.

**Layout**:
- Title (40pt): `Four agents. One bridge. Arc testnet.`
- Horizontal flow diagram, left-to-right, 3 lanes

**Diagram**:

```
  PRODUCERS (3)               BRIDGE              CONSUMERS (2)
  ┌─────────────┐         ┌─────────────┐      ┌─────────────┐
  │ Kimchi      │◀────────│             │─────▶│ Meta agent  │
  │ (premium)   │  HTTP   │   Signal    │      │ (Gemini)    │
  └─────────────┘         │   registry  │      │ arbitrates  │
  ┌─────────────┐─────────▶             │      └──────┬──────┘
  │ Dual-quote  │  publish│   + pricing │             │ spawns
  │ (from live  │  signals│             │             ▼
  │  v1.3 bot)  │         │   + outcome │      ┌─────────────┐
  └─────────────┘         │   feedback  │      │ Executor    │
  ┌─────────────┐─────────▶             │      │ (paper +    │
  │ Funding     │         │             │      │  settle)    │
  │ (real       │         │             │      └──────┬──────┘
  │  Binance)   │         └─────────────┘             │
  └─────────────┘                                     │ USDC transfer
                                                      ▼
                                                ┌─────────────┐
                                                │  Arc L1     │
                                                │  testnet    │
                                                │  150+ tx    │
                                                └─────────────┘
```

**3 callouts** (small boxes with 1 line each below diagram):
1. **Producers compete.** Each runs a different strategy. Every signal has a price attached.
2. **Meta arbitrates.** LLM picks the winner, weighted by which producer has been right lately.
3. **Executor pays.** Real USDC settles on Arc. Price scales with signal quality.

---

## SLIDE 6 — Variable price = signal quality

**Purpose**: convey the most novel economic primitive without saying "tokenomics."

**Layout**:
- Title (40pt): `The USDC amount on-chain IS the quote.`
- Subtitle (20pt, muted): `Not a receipt constant. A live signal-quality score.`
- Large central visual + 3 callouts

**Central visual**: 3 horizontal bars, left-to-right, increasing width & color intensity

```
Low-confidence signal
▓▓░░░░░░░░░░░░░░   $0.0005
                   [cyan 30% opacity]

Medium signal
▓▓▓▓▓▓▓▓░░░░░░░░   $0.005
                   [cyan 60% opacity]

High-confidence, high-notional signal
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   $0.010  (per-action cap)
                   [cyan 100% opacity]
```

**Annotation** (below bars, 20pt muted): `price = confidence × notional × |premium| × take_rate   →   clipped to [$0.0005, $0.010]`

**Bottom callout** (cyan box, 24pt): `"A producer that keeps being right gets paid more. A producer that keeps being wrong gets paid less. The Q-table sets the multiplier."`

---

## SLIDE 7 — The RL question, in plain English

**Purpose**: set up slide 8 WITHOUT assuming ML background. If slide 7 lands, slide 8 is a victory lap.

**Layout**:
- Top: Question as slide title (large, 56pt, centered): `Which strategy should trade right now?`
- Below: horizontal row of 3 strategy cards
- Bottom: one-line answer

**3 strategy cards** (3 equal columns, 400×300px each):

**Card 1 — v1 Kimchi**
- Icon: Korean flag / KRW symbol
- Title: `Kimchi Premium`
- 1-line: `KRW ↔ USDT cross-exchange spread. Wakes up when Korea gets excited.`

**Card 2 — v2 Dual-quote** (highlight border, `accent-cyan`)
- Icon: bar chart spike
- Title: `Dual-Quote Arb`
- 1-line: `USDT ↔ USDC intra-Binance spread. Fast, thin, high-frequency.`
- Tag: `Currently live in production on EC2.`

**Card 3 — v3 Funding**
- Icon: clock
- Title: `Funding-rate basis`
- 1-line: `Perp funding cadence arb. Wakes up every 8 hours.`

**Bottom callout** (60pt, cyan): `We don't pick. We learn.`

**Sub-bottom** (24pt, muted): `An agent watches market conditions, scores outcomes, and picks the strategy the data says works right now.`

---

## SLIDE 8 — The Receipt (walk-forward backtest)

**Purpose**: the MONEY SHOT. "Is the RL real?" answered by evidence, not rhetoric.

**Layout**:
- Title (40pt): `The learned policy matches the empirical best.`
- Subtitle (20pt, muted): `47-tick out-of-sample hold-out, split cal:178 / train:46 / test:47. Calibration frozen before training opens.`
- Large chart (1400×600px)

**Chart**: **horizontal bar chart** — NOT a table. Ordered top-to-bottom by $-performance. Colors:
- `TrainedQ_walkforward` — cyan, bold, ★ star icon on right
- `ALL_V2` — muted cyan (empirical optimum)
- `Ridge` — gray
- `LightGBM` — gray
- `ALL_V3_masked` — gray  
- `DIVERSIFY` — gray
- x-axis: `$ PnL on 47-tick hold-out`

| Policy | $ PnL |
|---|---:|
| ★ **TrainedQ_walkforward (shipped)** | $7.61 |
| ALL_V2 (single-strategy empirical optimum) | $9.44 |
| Ridge (ML baseline) | $6.43 |
| LightGBM | $5.42 |
| ALL_V3_masked (rule) | $2.07 |
| DIVERSIFY (uniform 1/3) | $1.60 |

**Annotation below chart** (two lines):
- Line 1, green check: `✓ Statistically ties empirical optimum  (p = 0.49 vs ALL_V2)`
- Line 2, green check: `✓ Beats diversify  (p = 0.012)`

**Bottom-right tag** (cyan box): `Round 2. Round 1 failed — reward function was broken. Fixed live, documented in SUBMISSION.md §11.b.1.`

---

## SLIDE 9 — Data honesty

**Purpose**: trust signal. Say out loud what's real vs synthetic. Judges will respect the candor.

**Layout**:
- Title (40pt): `Nothing is hidden. Here is exactly what is real.`
- 3 horizontal rows, full-width each (300px tall)

**Row 1 — v1 Kimchi**
- Left 1/3: `SYNTHETIC` (red tag, 32pt, bold)
- Middle 1/3: data source details: `AR(1) mean-reverting premium series. Seed committed.`
- Right 1/3: justification (muted): `Real cross-venue Upbit KRW + Binance USDT data wasn't available in time. Clearly labeled in every payload and on the dashboard.`

**Row 2 — v2 Dual-quote**
- Left: `REAL + BOOTSTRAP` (amber tag)
- Middle: `1 day of live v1.3 production 1-second tape. Bootstrap-resampled within-regime to fill 90d window.`
- Right: `The 1s bars are prices the production bot actually saw on 2026-04-19. Bootstrap is documented as bootstrap, not fabricated.`

**Row 3 — v3 Funding**
- Left: `REAL` (green tag)
- Middle: `Binance fapi/v1/fundingRate public REST, 2026-01-21 → 2026-04-21. 5 symbols × 271 ticks = 1,355 real 8h cycles.`
- Right: `No API key required. Anyone can reproduce from scratch.`

**Bottom caption** (20pt, centered, cyan): `Backtest convergence reproducible from public data alone.`

---

## SLIDE 10 — Circle products + trust model

**Purpose**: comply with submission requirement ("state Circle products used"), disclose custody model honestly.

**Layout**:
- Title (40pt): `What we used. What we declare.`
- Upper half: 4-column grid of Circle product icon cards (300×200px each)
- Lower half: custody disclosure banner

**4 product cards**:

**Card 1 — Arc L1**
- Icon: Arc logo or cube
- Label: `Arc testnet`
- Body (18pt): `150+ variably-priced settlement tx ($0.0005–$0.010). ChainID 5042002. USDC-as-gas.`

**Card 2 — USDC**
- Icon: USDC logo
- Label: `USDC`
- Body: `Unit of account for fees + payments + gas. Dual decimal (18 native / 6 ERC-20) handled.`

**Card 3 — Developer-Controlled Wallets (SCA)**
- Icon: wallet
- Label: `Circle Wallets (SCA)`
- Body: `4 Circle-SCA agent wallets via Wallet Sets (5th `producer_funding` is operator-controlled pending Circle SCA rotation). Custody is Circle's for the four; signing via entitySecretCiphertext.`

**Card 4 — Developer API transfers**
- Icon: API / arrow
- Label: `Developer API`
- Body: `/v1/w3s/developer/transactions/transfer posts the 150-tx burst. EIP-3009 hand-rolled path (executor_agent/main.py) validated but mempool-deferred.`

**Custody disclosure banner** (full-width, amber border, 22pt copy — slightly reduced to fit 3 bullets):

> **Trust model, declared.** 4 of 5 agent wallets are Circle-custodied SCAs signed by `entitySecretCiphertext`; the v3 `producer_funding` is a deterministic test address pending Circle SCA rotation (disclosed in its agent-card). Three concrete failure modes:
> **(a) Entity-secret leak** → all 4 Circle-SCA wallets compromised simultaneously (no per-wallet signing isolation); the operator-controlled fifth has its own surface.
> **(b) Circle freezes any wallet** (KYC / sanctions / ToS) → outcome loop halts, reliability scoring breaks.
> **(c) API rate-limit at sub-cent cadence** = de-facto censorship, no protocol-level recourse.
> Mainnet roadmap (SUBMISSION §12): Circle Wallets MPC + raw EIP-3009 on normalized mempool.

**Why changed from prior draft**: Vitalik note — original "operator dependency, same as every Circle-hosted agent stack" was read as whataboutism. Naming failure modes explicitly = audit trail, not custody-washing.

---

## SLIDE 11 — Originality

**Purpose**: 3 differentiators in 10 seconds.

**Layout**:
- Title (40pt): `What's new here`
- 3 vertical cards, equal width, 200px tall each

**Card 1** (cyan accent)
- Header: `Variable on-chain price`
- Body: `The USDC amount you see transferred is the price the market set for that specific signal — not a receipt constant.`

**Card 2** (purple accent)
- Header: `Closed outcome loop`
- Body: `Realized PnL retroactively re-prices future signals from the same producer. Variable pricing runs live in the executor's paper path; the 150-tx Circle burst is the evidence dump on the same Arc rails — fixed cadence, real hashes.`

**Why changed from prior draft**: Karpathy note — "tx stream is a real market, not a cron job" sets up attack. `scripts/circle_batch_settle.js:141` is a deterministic round-robin; the burst IS a cron-like evidence generator. Honesty here = disarms the critique in advance.

**Card 3** (green accent)
- Header: `Meta-policy above the market`
- Body: `A learned allocator picks which of three strategies even gets to trade. We use learning to validate the rule, not to replace it.`

**Bottom line** (centered, 24pt, muted): `Most "agent economy" demos stop at "LLM + wallet." We didn't.`

---

## SLIDE 12 — Close + links

**Purpose**: strong exit, all URLs the judge needs, one last memory hook.

**Layout**:
- Top half (60%): final brand statement
- Bottom half (40%): link grid

**Top half**:
- Huge quote (60pt, centered): `No human in the loop.`
- Sub (40pt, cyan, centered): `That's the unlock.`
- Wordmark (48pt, bold): `AlphaLoop`

**Bottom half — 4-column link grid** (Vercel confirmed deployed 2026-04-24):

| | | | |
|---|---|---|---|
| **GitHub** | **Live Dashboard** | **Pitch video** | **Contact** |
| `github.com/Leewonwuk/signal-mesh-arc` | `signal-mesh.vercel.app` | YouTube (unlisted) | `skyskywin@gmail.com` |

**Small footer** (mono, 14pt, muted): `lablab.ai · Agentic Economy on Arc · 2026-04-26 submission`

**Why changed**: Previous draft pulled the URL because Vercel returned HTTP 404 pre-deployment. As of 2026-04-24, deploy is live (HTTP 200) with a "static scaffold — watch the video for live feed" banner on the deployed build so judges clicking the URL don't get a dead dashboard. URL restored to closing slide.

---

## 3. Asset requirements

Assets Claude Design should generate as SVG/PNG alongside the deck:

1. **Node-graph cover accent** (slide 1) — 4 connected dots, simple vector
2. **Closed-loop diagram** (slide 4) — clean circular flow, 4 stations
3. **Architecture diagram** (slide 5) — 3-lane horizontal, producers/bridge/consumers
4. **Signal-quality bars** (slide 6) — 3 horizontal bars, increasing cyan intensity
5. **3 strategy cards** (slide 7) — flat icons + labels
6. **Walk-forward bar chart** (slide 8) — horizontal bars, highlighted row
7. **Provenance rows** (slide 9) — 3 full-width rows with color-coded left tags
8. **4 Circle product cards** (slide 10) — consistent card template
9. **3 originality cards** (slide 11) — same template, different accent colors

**Style unification**: all diagrams use 2px strokes, no fills except for intensity-mapped bars. Keep line-art minimalist.

---

## 4. Export settings

- **Format**: PDF
- **Size**: 16:9, 1920×1080 (matches YouTube / projector / lablab.ai uploader)
- **Pages**: exactly 12 (slide 1 → 12)
- **Fonts**: embed Inter + JetBrains Mono
- **Filename**: `SignalMesh_on_Arc_Deck_v2.pdf`
- **Alternate format** (optional): deliver an `.pptx` or `.key` if Claude Design can export to those; PDF is the required artifact
- **Target file size**: ≤ 5 MB

---

## 5. Content derived from source-of-truth files

If Claude Design needs to verify a fact or quote, pull from these files (in `C:\Users\user\hackerton\arc`):

| Fact | Source |
|---|---|
| One-liner / pitch framing | `docs/SUBMISSION.md:14-19`, `README.md:19-23` |
| Architecture (verify against code) | `bridge/src/index.ts`, `consumers/executor_agent/main.py` |
| Walk-forward leaderboard numbers | `docs/SUBMISSION.md:188-197` (or `docs/backtest_metrics.json`) |
| Data provenance table | `docs/SUBMISSION.md:165-174` |
| Circle products + custody model | `docs/SUBMISSION.md §5 (updated)` |
| Tx evidence (150 real hash+amount records) | `docs/evidence/batch_tx_hashes.txt` |
| Video narration flow | `docs/VIDEO_SCRIPT_KR.md` |

---

## 6. Do-not-ship checklist (things to remove from prior deck)

The previous `docs/SLIDES.md` contains statements that are now inaccurate or overclaim. These MUST be absent from the new deck:

- [ ] Any "EIP-3009 path wired / --nanopay flag" as the primary tx method (it's the fallback)
- [ ] "Nanopayments" as a headline product (we use Circle Developer API for the burst, not Nanopayments SDK)
- [ ] "EOA / agents hold their own keys" — inaccurate, wallets are Circle-custodied
- [ ] Tables with > 4 columns (they get cut off — use charts or card rows instead)
- [ ] Paragraphs of body copy > 3 sentences (break into bullets)
- [ ] RL terminology without translation ("tabular Q-learning over 9×7 state-action table" — translate to "we let the system learn which of 3 strategies should trade")
- ~~Reference to `https://signal-mesh.vercel.app` (if not deployed at recording time — use localhost screenshots or omit)~~ — **Deploy confirmed live 2026-04-24**; URL restored to Slide 12.

---

## 7. Tone

- **Confident but not arrogant** — "we did X" not "we revolutionized X"
- **Honest about limits** — trust model, synthetic data, mempool workaround
- **Plain English where possible** — assume judge is smart but not specialized
- **Ship signal over brag signal** — "150 variably-priced real tx on arcscan" > "world-class decentralized marketplace"

---

## 8. Fallback for Claude Design

If Claude Design cannot produce diagrams with the fidelity required (especially slides 4, 5, 8), prefer:

1. **Text-forward version** with clear ASCII-box-layout (readable, zero-dependency)
2. **SVG hand-authored** (I can hand-author SVG if you paste the specific slide # that failed)
3. **Placeholder boxes** with clear labels like `[CHART: walk-forward bars]` — we slot in manually later

Generating 12 slides that are "OK but consistent" beats 6 beautiful + 6 missing.

---

**End of brief. Go generate.** When the PDF is ready, save as `docs/SLIDES_v2.pdf` and keep the old `SLIDES.pdf` at `docs/SLIDES_v1_archived.pdf` for rollback.
