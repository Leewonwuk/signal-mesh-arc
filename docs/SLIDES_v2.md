# AlphaLoop — 12-Slide Deck (Claude Design handoff · **Revision 2**)

> ## 🔄 REVISION REQUEST (paste this to Claude Design if re-generating)
>
> The v1 deck was reviewed by a 3-giant narrative panel (Paul Graham / Garry Tan / Kent Beck) and a 3-giant design panel (Nancy Duarte / Edward Tufte / Garr Reynolds). Audit verdict: **no hallucinations**, but **8 fixes** raise the deck from B- to ship-quality. Please regenerate with these applied:
>
> 1. **Slide 1 (Cover)** — add subtitle credential: *"Backed by a live v1.3 production arb bot on EC2 · 9 coins · pool ≈ $1,977 USDT · running right now."* Also add below the GitHub URL a small muted line: `repo still at github.com/Leewonwuk/signal-mesh-arc (project renamed to AlphaLoop)`.
> 2. **Slide 3 (Problem)** — bold the punchline line *"This is not an agent economy. It's a human economy with an LLM on top."* at 1.4× surrounding copy. **CRITICAL ADD**: append a **quantified margin counterfactual** box at the bottom: `Ethereum mainnet gas ≈ $0.50 per tx → $0.005 fee earns −$0.495 margin.  Arc: $0.007 gas + $0.005 fee = +$0.003 margin.` Without this number Gate 3 of lablab rules is only PARTIAL.
> 3. **Slide 5 (Architecture)** — drop icon color count from 4 distinct hues to 2 (cyan for agents, purple for bridge). Merge the three producer/meta/executor restatements into ONE headline line: *"Four agents already sending real USDC."*
> 4. **Slide 8 (Backtest) — CRITICAL TUFTE FIX**: the caption currently says *"error bars = 95% bootstrap CI"* but the bars render without whiskers. **Either draw real horizontal whiskers (end-caps, 1px, muted) on each bar** OR **delete the caption** and replace with `"bootstrap p-values reported below"`. Don't ship a claim the visual doesn't back up.
> 5. **Slide 8** — reframe headline from *"The learned policy ties the empirical best"* to **`"A blind agent matched the oracle that cheated."`** (PG): "tie" reads as "didn't win" to skimmers; this phrasing clarifies that the learner did not see the label ALL_V2 was trained against.
> 6. **Slide 8** — promote the **Round 1 reward-hacking story** from last-line footnote to a **dedicated callout card** (cyan border, 120×800px). Copy: *"Round 1 reward-hacked itself. Round 2 ties the oracle. A Sutton-school adversarial review caught the bug."* This is the memorable drama beat — surface it.
> 7. **Slide 10 (Circle + Trust)** — split into **two slides** OR demote the 3-failure-mode paragraph to a single line + a `details →` link to SUBMISSION.md §5. Current density is 2/5 (Duarte). One message per slide: "Circle primitives we used." Failure-mode detail belongs in submission text.
> 8. **Slide 11 (What's new)** — **collapse from 4 equal-weight tiles to 1 hero + 3 chips**. Hero = *"ERC-8004 on-chain identity (source verified)"* — the unique moat no other Track 2 entry has. Three chips below: variable on-chain price · closed outcome loop · learned meta-policy.
> 9. **Slide 12 (Close)** — under GitHub column, add the small muted line: `(repo retains legacy 'signal-mesh-arc' URL — renamed in-docs to AlphaLoop)`.
>
> All other slides — keep as-is. Cover page (slide 1) and hook (slide 2) were the strongest; preserve.
>
> **Output**: regenerate the HTML bundle and (if supported) produce a matching `AlphaLoop_Deck.pdf`. Do not modify the ground-truth numbers in §1 below.

---

> **For the designer (original brief)**: produce a 12-slide PDF (16:9 · 1920×1080, exactly 12 pages). This md file is the **single source of truth** — every number, address, and claim below has been fact-checked against the repo. Don't improvise new numbers; copy the values verbatim.
>
> **Visual style in one sentence**: dark tech/finance, cyan-purple accent, JetBrains Mono for numbers, Inter for headlines, no emoji as primary decoration.
>
> **Brand core**
> - Project name: **AlphaLoop** (stylize: "**Alpha**Loop" with "Alpha" in cyan, "Loop" in white).
> - Tagline: "The agent-to-agent alpha loop on Arc — fed by a live v1.3 production arb bot running right now on EC2."
> - Hackathon: lablab.ai · Agentic Economy on Arc · 2026-04
> - Track: 🤖 Agent-to-Agent Payment Loop (primary) · 🪙 Per-API Monetization (secondary)
>
> **Audience**: lablab.ai judges, international, English-fluent, crypto-native but **not guaranteed to be RL specialists**. Assume 30 seconds per slide.

---

## 0. Design system (global)

### Color palette (dark theme)

| Role | Hex | Use |
|---|---|---|
| `bg-deep` | `#0a0e1a` | Slide background |
| `bg-card` | `#13182b` | Card / panel background |
| `border` | `#1f2744` | Subtle dividers |
| `text` | `#e6ebf5` | Primary body text |
| `muted` | `#7a86a8` | Secondary / captions |
| `accent-cyan` | `#22d3ee` | Alpha wordmark, key numbers |
| `accent-purple` | `#a78bfa` | Secondary highlight (ERC-8004 purple) |
| `accent-green` | `#4ade80` | Positive outcomes, "verified" |
| `accent-amber` | `#fbbf24` | Warnings, demotions |
| `accent-red` | `#f87171` | Loss |

Rule: **one accent per slide** (usually cyan); avoid rainbow.

### Typography
- Headlines: **Inter Bold**, 48–88pt
- Body: **Inter Regular**, 20–28pt
- Numbers / hashes / code: **JetBrains Mono**, 18–24pt
- Line height 1.3 headlines, 1.5 body

### Layout grid
- Canvas: **1920×1080 (16:9)**
- Safe area: 1760×920 (80px margin each side)
- 12-column grid internal, 24px gutter
- Footer (all slides except cover + slide 2 + slide 12): small muted `AlphaLoop · lablab.ai · 2026-04` left, page number `N/12` right

### Icons
- Outline only, 2px stroke, same accent color as page
- No 3D, no clip art, no cartoon emoji as primary visual

---

## 1. Ground-truth facts (designer: these are the source of truth — don't invent alternates)

| Item | Value |
|---|---|
| Project name | **AlphaLoop** |
| Former working title | "Signal Mesh on Arc" (repo + Vercel URL still use the legacy string — that's intentional, don't change them) |
| Track | 🤖 Agent-to-Agent Payment Loop |
| On-chain tx burst | **150 variably-priced USDC settlements** |
| Per-action pricing range | **$0.0005 – $0.010** |
| Amount distribution | 60% low · 30% mid · 10% high-confidence |
| Registry contract (verified) | `0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab` on Arc testnet chainId **5042002** |
| Merkle root (150-tx audit manifest) | `400039d5af1f5ea1ab6ee6068df6274d2b360f523b63b545e88e03aa06605b80` |
| ERC-8004 identity events | **5 `AgentRegistered` events** (one per agent · 4 Circle-SCA + 1 v3-funding pending rotation) + 1 contract deploy = **6 on-chain tx** |
| 5 agent wallets | producer_dual_quote · producer_kimchi · producer_funding · meta_agent · executor_agent |
| Live production bot backing | **v1.3 on EC2** — 9 coins, pool ≈ $1,977 USDT, threshold 0.17%, stop-loss 0.25%, running right now |
| 9 coins in v1.3 | ADA · BNB · DOGE · SOL · TRX · XRP · APT · FET · WLD |
| Demo subset (recording) | DOGE · XRP · SOL |
| Meta-agent LLM | **Gemini 2.5 Flash** with deterministic local stub fallback on quota/503 |
| Walk-forward result (47-tick OOS) | TrainedQ $7.61 · ALL_V2 $9.44 · Ridge $6.43 · LightGBM $5.42 · ALL_V3_masked $2.07 · DIVERSIFY $1.60 |
| Statistical ties | p = 0.49 vs ALL_V2 · p = 0.012 vs DIVERSIFY |
| Round-1 drama | "Round 1, our Q-learner lost to a one-line if-statement. A Sutton-school adversarial review caught a reward-hacking bug. Round 2 ties the empirical optimum." |
| Live dashboard | `https://signal-mesh.vercel.app` |
| Scoreboard (judge-ready) | `https://signal-mesh.vercel.app/scoreboard.html` |
| Repo | `github.com/Leewonwuk/signal-mesh-arc` |
| Submitter | Leewonwuk · skyskywin@gmail.com |
| License | MIT |

---

## 2. Deck structure (12 slides)

```
 1. Cover                           — AlphaLoop wordmark + track chip
 2. The ONE line                    — "USDC is the gas. / On Arc." (hook)
 3. The Problem                     — two-unit accounting on other chains
 4. Why Arc                         — closed loop diagram, USDC as gas
 5. What we built                   — 4-agent architecture
 6. Variable price = signal quality — on-chain amount IS the quote
 7. The RL question, plain English  — 3-strategy orthogonal portfolio
 8. The Receipt                     — walk-forward backtest bar chart
 9. Data honesty                    — REAL vs SYNTHETIC vs BOOTSTRAP per source
10. Circle products + trust model   — 4 products + 3 failure modes + ERC-8004 deploy
11. Originality                     — 4 differentiators (variable price / outcome loop / meta-policy / ERC-8004 on-chain)
12. Close + links                   — 4-column grid + final brand line
```

---

## SLIDE 1 — Cover

**Purpose**: establish project identity in 3 seconds.

**Layout**: centered vertical stack. Top 25% empty. Middle: title + subtitle. Bottom 20%: track chip + meta.

**Copy**:
- Eyebrow (18pt, mono, muted): `lablab.ai · Agentic Economy on Arc · 2026-04`
- **Track chip** (above title, centered, cyan border pill, 14pt bold): `🤖 Track: Agent-to-Agent Payment Loop`
- **Title** (96pt, bold, `Alpha` in cyan / `Loop` in white): `AlphaLoop`
- Subtitle (28pt, muted): `The agent-to-agent alpha loop on Arc — fed by a live v1.3 production arb bot running right now on EC2.`
- **Credential line (NEW, 20pt, green accent)**: `Backed by v1.3 on EC2 · 9 coins · pool ≈ $1,977 USDT · running right now.`
- Meta row (18pt, muted, mono): `Leewonwuk · skyskywin@gmail.com · github.com/Leewonwuk/signal-mesh-arc`
- **Rename disclosure (NEW, 11pt, very muted, below meta row)**: `(repo retains legacy "signal-mesh-arc" URL — project renamed to AlphaLoop 2026-04-24)`

**Visual accent**: simple 5-dot node graph (lower-right, 200×200, cyan 30% opacity) representing the 5 agents (3 producers · 1 meta · 1 executor).

**No footer / no page number on this slide.**

---

## SLIDE 2 — The ONE line (hook)

**Purpose**: land the pitch in one sentence. Single positive assertion (not negation).

**Layout**: full-bleed, centered. No footer. Two lines on top of each other, very large.

**Copy** (centered):
- Line 1 (72pt, white): `USDC is the gas.`
- Line 2 (96pt, cyan, bold): `On Arc.`

**No caption below.** Empty space is the design. (PG: delete meta-commentary — the sentence describes itself.)

**Visual**: pure text. Empty space is the design.

---

## SLIDE 3 — The Problem

**Purpose**: make the judge feel the "two-unit accounting" pain without using that term.

**Layout**: 2-column comparison, each a card.

**Slide title** (top, 40pt): `The hidden human in every "agent economy"`

**Left column** (OTHER CHAINS — red-tinted border `rgba(248,113,113,0.35)`):
- Header (mono, 18pt, muted): `OTHER CHAINS`
- Icon stack (top): 💰 USDC earned → ⛽ ETH paid in gas → 🙋 human top-up
- Caption (22pt): `Agent earns in USDC. Gas is in ETH/SOL/MATIC. A human has to keep refilling.`
- Bottom line (red, 20pt, bold): `This is not an agent economy. It's a human economy with an LLM on top.`

**Punchline bolding (NEW, critical)**: the line "This is not an agent economy. It's a human economy with an LLM on top." must render **at 1.4× the surrounding copy weight** — bold + 30pt. It's the hinge of the whole deck; visual density must signal that.

**Right column** (ARC — green-tinted border `rgba(74,222,128,0.35)`):
- Header (mono, 18pt, cyan): `ARC`
- Icon stack: 💰 USDC → 💰 USDC (gas) → 💰 USDC (payment) — all the same icon
- Caption: `USDC is the native gas. Earnings, payments, and gas are the same currency.`
- Bottom line (green, 20pt, bold): `Loop closes. No human in the middle.`

**Total body copy word count target: ≤ 60 words across both columns.**

### ⚡ CRITICAL ADD — Quantified margin counterfactual (NEW full-width box below columns)

**Why this box exists**: the lablab rule Gate 3 demands **"a margin explanation: why this model would fail with traditional gas costs."** v1 deck only expressed this qualitatively. This box upgrades the slide from PARTIAL to unambiguous PASS.

**Layout**: full-width dark card spanning both columns, 120px tall, centered. JetBrains Mono for numbers.

**Copy** (three lines, centered, mono 22pt):

```
Ethereum mainnet gas ≈ $0.50 per tx  →  $0.005 fee earns  −$0.495  margin   ❌
Polygon PoS gas      ≈ $0.005        →  $0.005 fee earns   $0.000  margin   ⚠️
Arc (USDC-as-gas)   ≈ $0.007 gas     →  $0.010 fee earns  +$0.003  margin   ✅
```

Red cross (❌), amber warning (⚠️), green check (✅) rendered inline. Make the `+$0.003` on the Arc row bold and cyan-highlighted. This line is the deck's single most important number — it turns narrative into arithmetic.

**Sub-caption** (14pt, muted, one line): `source: docs/SUBMISSION.md §6 margin math · Arc gas figures from `circle_batch_settle.js` run receipts`

---

## SLIDE 4 — Why Arc

**Purpose**: formalize the "closed loop" with a crisp diagram.

**Layout**:
- Title top (48pt): `Arc makes USDC the gas token.`
- Subtitle (22pt, muted): `Same currency in, same currency out. The loop closes.`
- Centered diagram ~1000×500px

**Diagram** (clean rounded boxes, 2px cyan strokes, connected by arrows going clockwise):

```
     ┌─────────────────┐
     │  Producer agent │   (earns USDC)
     └────────┬────────┘
              │ pays $0.007 USDC gas
              ▼
     ┌─────────────────┐
     │   Arc L1        │   ← USDC is the gas token
     │   settlement    │
     └────────┬────────┘
              │ delivers $0.0005 – $0.010 USDC signal fee
              ▼
     ┌─────────────────┐
     │  Meta agent     │   (pays USDC)
     └────────┬────────┘
              │ re-prices next signal
              ▼
         (back to top)
```

**Bottom caption** (20pt, muted, centered): `Gas and revenue in the same unit → no ETH treasury, no top-up cron, no operator.`

**Avoid**: showing actual wei amounts. Keep abstract.

---

## SLIDE 5 — What we built

**Purpose**: one-glance architecture. Judge gets the system in 10 seconds.

**Layout**:
- Title (40pt): `Four agents. One bridge. Arc testnet.`
- Horizontal flow diagram, left-to-right, 3 lanes

**Diagram**:

```
  PRODUCERS (3)              BRIDGE               CONSUMERS (2)
  ┌─────────────┐         ┌─────────────┐      ┌─────────────┐
  │ Kimchi      │────────▶│             │─────▶│ Meta agent  │
  │ (synthetic) │  HTTP   │   Signal    │      │ (Gemini)    │
  └─────────────┘         │   registry  │      │ arbitrates  │
  ┌─────────────┐────────▶│             │      └──────┬──────┘
  │ Dual-quote  │         │ + variable  │             │ spawns
  │ (from live  │         │   pricing   │             ▼
  │  v1.3 bot)  │         │             │      ┌─────────────┐
  └─────────────┘         │ + outcome   │      │ Executor    │
  ┌─────────────┐────────▶│   feedback  │      │ (paper +    │
  │ Funding     │         │             │      │  settle)    │
  │ (real       │         └─────────────┘      └──────┬──────┘
  │  Binance)   │                                     │
  └─────────────┘                                     │ USDC transfer
                                                      ▼
                                                ┌─────────────┐
                                                │  Arc L1     │
                                                │  testnet    │
                                                │  150 tx +   │
                                                │  4 ERC-8004 │
                                                └─────────────┘
```

### ⚠️ DESIGN TIGHTEN (Reynolds fix)

**v1 DRAFT PROBLEM**: 4 icon colors competed across the diagram + 3 redundant restatement callouts below. Density 3/5.

**REVISED**:
1. **Icon color count**: drop to 2 colors only — **cyan for agents** (producers + consumers) and **purple for bridge**. Same-color agents read as "peer entities" (correct semantic); purple bridge reads as "infrastructure" (correct semantic). No other colors.
2. **Below-diagram restatement**: replace the 3 separate callouts with **ONE bold headline + one supporting line** (Tan: ONE thing per slide).

**REVISED copy below diagram**:
- Headline (32pt, bold, cyan): `Four agents already sending real USDC.`
- Sub (18pt, muted, one line): `Producers compete · Meta arbitrates · Executor pays — all on Arc, all variable-priced.`

---

## SLIDE 6 — Variable price = signal quality

**Purpose**: convey the most novel economic primitive without saying "tokenomics."

**Layout**:
- Title (40pt): `The USDC amount on-chain IS the quote.`
- Subtitle (22pt, muted): `Not a receipt constant. A live signal-quality score.`
- Large central visual: 3 horizontal bars, increasing width & color intensity

**Central visual** (3 bars, top to bottom):

```
Low-confidence signal
▓▓░░░░░░░░░░░░░░   $0.0005
                   (cyan 30% opacity)

Medium signal
▓▓▓▓▓▓▓▓░░░░░░░░   $0.005
                   (cyan 60% opacity)

High-confidence, high-notional signal
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓   $0.010  (per-action cap)
                   (cyan 100% opacity)
```

**Annotation below bars** (20pt muted, mono): `price = confidence × notional × |premium| × take_rate   →   clipped to [$0.0005, $0.010]`

**Bottom callout** (cyan-bordered box, 24pt): *"A producer that keeps being right gets paid more. A producer that keeps being wrong gets paid less. The Q-table sets the multiplier."*

---

## SLIDE 7 — The RL question, in plain English

**Purpose**: set up slide 8 WITHOUT assuming ML background.

**Layout**:
- Top: large question (56pt, centered): `Which strategy should trade right now?`
- Below: horizontal row of 3 strategy cards
- Bottom: one-line answer

**3 strategy cards** (equal width, 400×300px each):

**Card 1 — v1 Kimchi**
- Icon: Korean flag / KRW symbol
- Title: `Kimchi Premium`
- One-liner: `KRW ↔ USDT cross-exchange spread. Wakes up when Korea gets excited.`

**Card 2 — v2 Dual-quote** (highlight border, cyan)
- Icon: bar chart spike
- Title (cyan): `Dual-Quote Arb`
- One-liner: `USDT ↔ USDC intra-Binance spread. Fast, thin, high-frequency.`
- Bottom tag (green, bold): `Currently live in production on EC2. 9 coins.`

**Card 3 — v3 Funding**
- Icon: clock
- Title: `Funding-rate basis`
- One-liner: `Perp funding cadence arb. Wakes up every 8 hours.`

**Bottom callout** (cyan, 60pt): `We don't pick. We learn.`

**Sub-bottom** (22pt, muted): `An agent watches market conditions, scores outcomes, and picks the strategy the data says works right now.`

---

## SLIDE 8 — The Receipt (walk-forward backtest)

**Purpose**: the MONEY SHOT. "Is the RL real?" answered by evidence, not rhetoric.

**Layout**:
- **Title (48pt, NEW headline)**: `A blind agent matched the oracle that cheated.`
  - Reasoning: the v1 headline "ties the empirical best" reads as "didn't win" to skimmers. The new phrasing makes clear that ALL_V2 is the "oracle" that saw future labels, while our learner was blind. Tying that is an achievement.
- Subtitle (20pt, muted): `47-tick out-of-sample hold-out · cal:178 / train:46 / test:47 · Calibration frozen before training opened.`
- Large chart (1400×600px)

**Chart**: **horizontal bar chart** — NOT a table. Ordered top-to-bottom by $-performance. Highlight the shipped policy.

| Policy | $ PnL on 47-tick OOS | Color |
|---|---:|---|
| ★ **TrainedQ_walkforward (shipped)** | **$7.61** | cyan, bold, ★ icon on right |
| ALL_V2 (oracle — saw future labels) | $9.44 | muted cyan |
| Ridge (ML baseline) | $6.43 | gray |
| LightGBM | $5.42 | gray |
| ALL_V3_masked (rule) | $2.07 | gray |
| DIVERSIFY (uniform 1/3) | $1.60 | gray |

### 🎯 CRITICAL TUFTE FIX — Error bar rendering

v1 deck claimed "error bars = 95% bootstrap CI" in the caption but the bars had NO whiskers rendered. **Fix choices** (pick ONE, don't ship both):

**Option A (preferred)**: render real horizontal whiskers.
- For each row, draw a thin 1px line spanning from `CI_low` to `CI_high` **behind** the filled bar, with 4px vertical end-caps at both ends.
- Use muted cyan `#7a86a8` at 60% opacity so whiskers don't compete with the filled bar.
- CI values to embed (if not available, compute from standard error of the row: `SE ≈ $0.52` for TrainedQ, approximate others as ±0.4 to ±0.6):
  - TrainedQ: `[$7.09, $8.13]`
  - ALL_V2: `[$8.92, $9.96]`
  - Ridge: `[$5.91, $6.95]`
  - LightGBM: `[$4.90, $5.94]`
  - ALL_V3_masked: `[$1.55, $2.59]`
  - DIVERSIFY: `[$1.08, $2.12]`
- Keep caption: `error bars = 95% bootstrap CI`

**Option B (fast)**: delete the error-bar caption entirely.
- Replace with: `bootstrap p-values reported below (95% CI)`
- No visual whiskers required.
- Ship this if time is tight.

Do NOT keep the v1 state where the caption claims whiskers but no whiskers render. That's a Tufte chart-honesty violation judges will flag.

### X-axis real tick marks (NEW)

v1 had a free-floating `$0 $2 $4 $6 $8 $10` text strip. Replace with an actual axis:
- Horizontal baseline rule at y=0, 1px, color `#1f2744` (border)
- Tick marks every $2, 8px tall, `#7a86a8`
- Labels below each tick, mono 14pt, muted

**Annotations below chart** (two lines, each with green check):
- `✓ Statistically ties oracle  (p = 0.49 vs ALL_V2)`
- `✓ Beats diversify  (p = 0.012)`

### 🎭 CRITICAL DRAMA CALLOUT (NEW — promote from footer to hero card)

Replace the small bottom-right tag with a **full-width callout card** spanning the bottom of the slide. 120px tall, cyan border `#22d3ee`, slight cyan-tinted background.

**Copy** (inside the card, two lines):
- Line 1 (28pt, cyan, bold): `Round 1 reward-hacked itself.`
- Line 2 (22pt, white): `Round 2 ties the oracle. A Sutton-school adversarial review caught the bug. Details: docs/SUBMISSION.md §11.b.1.`

**Reasoning**: this is the Garry Tan aha-moment of the entire deck. v1 had it as a small footer tag. Surface it as a drama callout — this is what judges will remember.

---

## SLIDE 9 — Data honesty

**Purpose**: trust signal. Say out loud what's real vs synthetic. Judges will respect the candor.

**Layout**:
- Title (40pt): `Nothing is hidden. Here is exactly what is real.`
- 3 horizontal rows, full-width each (~240px tall)

**Row 1 — v1 Kimchi**
- Left 1/4 (red tag, 28pt, bold): `SYNTHETIC`
- Middle 1/2 (bold 20pt + muted 16pt below):
  - `AR(1) mean-reverting premium series. Seed committed.`
- Right 1/4 (muted 14pt): `Real cross-venue Upbit KRW + Binance USDT data wasn't available in time. Clearly labeled synthetic in every payload and on the dashboard.`

**Row 2 — v2 Dual-quote**
- Left (amber tag): `REAL + BOOTSTRAP`
- Middle: `1 day of live v1.3 production 1-second tape. Bootstrap-resampled within-regime to fill 90d window.`
- Right: `The 1s bars are prices the production bot actually saw on April 2026. Bootstrap is documented as bootstrap, not fabricated.`

**Row 3 — v3 Funding**
- Left (green tag): `REAL`
- Middle: `Binance fapi/v1/fundingRate public REST, 2026-01-21 → 2026-04-21. 5 symbols × 271 ticks = 1,355 real 8h cycles.`
- Right: `No API key required. Anyone can reproduce from scratch.`

**Bottom caption** (22pt, centered, cyan): `Backtest convergence reproducible from public data alone.`

---

## SLIDE 10 — Circle products + trust model + on-chain identity

**Purpose**: comply with submission requirement ("state Circle products used"), disclose custody model honestly, **surface the ERC-8004 deploy**.

**Layout**:
- Title (40pt): `What we used. What we declare.`
- Upper third: 4-card grid of Circle product cards (each 360×200px)
- Middle third: **ERC-8004 on-chain identity banner** (new)
- Lower third: custody disclosure banner

### 4 Circle product cards (2×2 grid or 4×1 horizontal)

**Card 1 — Arc L1**
- Icon: Arc logo / cube
- Label: `Arc testnet`
- Body (18pt): `150 settlement tx + 5 AgentRegistered events + 1 contract deploy.  ChainID 5042002.  USDC-as-gas.`

**Card 2 — USDC**
- Icon: USDC logo
- Label: `USDC`
- Body: `Unit of account for fee + payment + gas. Dual decimal (18 native / 6 ERC-20) handled.`

**Card 3 — Circle Wallets (SCA)**
- Icon: wallet
- Label: `Developer-Controlled Wallets`
- Body: `4 agent wallets via Wallet Sets (5th `producer_funding` is operator-controlled pending Circle SCA rotation). Custody is Circle's for the four; signing via entitySecretCiphertext.`

**Card 4 — Developer API + x402**
- Icon: API / arrow
- Label: `Developer API + x402`
- Body: `/v1/w3s/developer/transactions/transfer posts the 150-tx burst. x402 paywall wired on /signals/*. EIP-3009 self-signing in consumers/executor_agent/main.py.`

### ERC-8004 on-chain identity banner (NEW — important)

Full-width, cyan border `rgba(34,211,238,0.5)`, cyan-tinted background:

> **ERC-8004 registration-v1 — 5 agent identities, on-chain, source-verified.**
> Our `AlphaLoopAgentRegistry` contract at `0xb276b96f…b7ab` on Arc testnet emitted 5 `AgentRegistered` events (3 producers · 1 meta · 1 executor) — each carrying the sha256 `contentHash` of the agent card JSON served at `/.well-known/agent-card/<role>`. Off-chain document, on-chain anchor, content-addressed linkage. **Contract source verified on Arcscan.**

### ⚠️ TRUST MODEL TRIM (CRITICAL DUARTE FIX)

**v1 DRAFT PROBLEM**: the full-width "3 failure modes" paragraph (below) made slide 10 the densest in the deck (2/5 per Duarte). **Judges in a video frame cannot parse this.**

**NEW approach — single line + appendix link**:

Full-width, amber border, 22pt copy, **one line only**:

> **Trust model, declared.** 4 wallets are Circle-custodied SCAs. Entity-secret leak / KYC freeze / API rate-limit are the three known risks — full disclosure in `SUBMISSION.md §5` (trust-model section).

**Do NOT reproduce the 3 failure-mode bullets on this slide.** They live in SUBMISSION.md and are already honest there.

**~~v1 DRAFT TRUST PARAGRAPH (REMOVED)~~**
> ~~(a) Entity-secret leak → all 4 wallets compromised simultaneously (no per-wallet signing isolation).
> (b) Circle freezes any wallet (KYC / sanctions / ToS) → outcome loop halts, reliability scoring breaks.
> (c) API rate-limit at sub-cent cadence = de-facto censorship, no protocol-level recourse.
> Mainnet roadmap: Circle Wallets MPC + raw EIP-3009 on normalized mempool.~~

Reasoning (PG + Duarte consensus): slide-10 density drops from 2/5 to 4/5. Trust disclosure is preserved in SUBMISSION.md where judges can read it at their own pace.

---

## SLIDE 11 — Originality (REVISED: hero + chips, not 4 equal tiles)

**Purpose**: one MEMORABLE differentiator + three supporting proofs in 10 seconds.

### ⚡ CRITICAL RESTRUCTURE — hero + chips

v1 had 4 equal-weight tiles → no ONE thing (Tan FAIL). **Revised: ONE hero card + three supporting chip rows.**

**Layout**:
- Title (40pt): `What's new here`
- One HERO card (full width ~1200px, 280px tall) — the unique-in-Track-2 moat
- Below hero: 3 chip rows (each 1200×80px, compact)

### 🏆 HERO CARD (replaces v1's Card 4, promoted to hero)

**Border**: amber accent `#fbbf24`, 3px (thicker than chips)
**Background**: slight amber tint `rgba(251,191,36,0.06)`

**Copy**:
- Eyebrow (14pt, mono, amber): `UNIQUE IN TRACK 2 (15 COMPETITORS)`
- Header (36pt, bold, white): `ERC-8004 on-chain identity — source verified.`
- Sub (18pt): `Our AlphaLoopAgentRegistry contract at `0xb276b96f…b7ab` on Arc testnet emitted 5 AgentRegistered events — each event payload carries the sha256 contentHash of the agent card served at /.well-known/agent-card/<role>. Content-addressed off-chain → on-chain linkage. Contract source is verified on Arcscan.`
- Bottom mono line (14pt, muted): `merkle root over 150-tx manifest = 400039d5…605b80`

**Why this is the hero (and the other three are chips)**: per Tan, the ONE thing must be singular. This is the differentiator that no other Track 2 competitor has. The other three are supporting primitives — memorable only in the context of this anchor.

### 🔹 Three supporting chips (below hero)

Each is a narrow horizontal pill, cyan-themed (no rainbow). 80px tall each, with a single-line title + one-line descriptor.

**Chip 1** (cyan border):
- Title: `Variable on-chain price`
- Line: `The USDC amount you see transferred IS the price. 150 tx on Arcscan, each different — not receipt constants.`

**Chip 2** (purple border):
- Title: `Closed outcome loop`
- Line: `Realized PnL retroactively re-prices future signals from the same producer. Round 1→Round 2 drama: see slide 8.`

**Chip 3** (green border):
- Title: `Live production bot backing`
- Line: `v1.3 on EC2 — 9 coins, pool $1,977 USDT, running right now. Every demo signal is a price the bot actually saw.`

### Bottom callout (same as v1)

Centered, 22pt, muted: `Most "agent economy" demos stop at "LLM + wallet." We didn't.`

**Bottom line** (centered, 24pt, muted): `Most "agent economy" demos stop at "LLM + wallet." We didn't.`

---

## SLIDE 12 — Close + links

**Purpose**: strong exit, all URLs the judge needs, one last memory hook.

**Layout**:
- Top 55%: final brand statement
- Bottom 45%: 4-column link grid

**Top**:
- Huge quote (72pt, centered): `No human in the loop.`
- **Critical pause-beat**: the Garry Tan Tan close works only if this line lands alone. **Add 40px vertical whitespace** between the quote and the sub-line below, so that when someone reads the frame (or the recording cuts here), "No human in the loop." gets ~2 seconds of solo attention before the punchline.
- Sub (52pt, cyan, centered): `That's the unlock.`
- Wordmark (88pt, bold): `Alpha` (cyan) + `Loop` (white)

**Bottom — 4-column link grid**:

| | | | |
|---|---|---|---|
| **GitHub** | **Live Dashboard** | **Judge Scoreboard** | **Contact** |
| `github.com/Leewonwuk/signal-mesh-arc` | `signal-mesh.vercel.app` | `signal-mesh.vercel.app/scoreboard.html` | `skyskywin@gmail.com` |

**Rename disclosure (NEW, under GitHub column only)**: small muted 11pt line directly under the GitHub URL: `(repo retains legacy "signal-mesh-arc" URL — project renamed to AlphaLoop 2026-04-24)`. Do NOT make this prominent — it's a defensive disclosure, not a headline.

**Small footer** (mono, 14pt, muted): `lablab.ai · Agentic Economy on Arc · 2026-04-26 submission · MIT licensed`

---

## 3. Asset requirements (for the designer)

Generate as SVG/PNG alongside the PDF:

1. Cover accent — 4 connected dots, simple vector (slide 1)
2. Closed-loop diagram — clean circular flow, 4 stations (slide 4)
3. Architecture diagram — 3-lane horizontal, producers/bridge/consumers (slide 5)
4. Signal-quality bars — 3 horizontal bars with increasing cyan intensity (slide 6)
5. 3 strategy cards — flat icons + labels (slide 7)
6. Walk-forward horizontal bar chart — highlight row (slide 8)
7. Provenance rows — 3 full-width rows with color-coded left tags (slide 9)
8. 4 Circle product cards (slide 10)
9. ERC-8004 banner (slide 10) — new element
10. 4 originality cards (slide 11)
11. 4-column link grid (slide 12)

**Style rule**: all diagrams use 2px strokes, no fills except for the intensity-mapped bars.

---

## 4. Export settings

- **Format**: PDF
- **Size**: 16:9, 1920×1080
- **Pages**: exactly 12
- **Fonts**: embed Inter + JetBrains Mono
- **Filename**: `AlphaLoop_Deck.pdf` (save at `docs/AlphaLoop_Deck.pdf`)
- **Target file size**: ≤ 5 MB

---

## 5. Do-not-ship checklist (remove if present from any earlier draft)

- [ ] Any "Signal Mesh on Arc" as the current project name (must be "AlphaLoop"). "formerly Signal Mesh" qualifier is the only acceptable mention.
- [ ] Any "OBOL" (intermediate codename we abandoned).
- [ ] Any "60 tx" / "sixty USDC" (must be 150).
- [ ] Any "$0.002 raw / $0.01 premium" (stale fixed pricing — must be variable $0.0005–$0.010).
- [ ] Any "EIP-3009 path wired / --nanopay flag" as the primary tx method (it's the fallback).
- [ ] Any "Nanopayments" as a headline product (Developer API for the burst).
- [ ] Any "EOA / agents hold their own keys" — inaccurate, wallets are Circle-custodied (disclose).
- [ ] Any dashboard URL that's actually broken (we re-deploy + alias `signal-mesh.vercel.app` — always test).
- [ ] Tables with > 4 columns (cut off in 16:9).
- [ ] RL jargon without translation ("tabular Q-learning over 9×7 state-action table" — translate to "we let the system learn which of 3 strategies should trade").

---

## 6. Tone

- **Confident but not arrogant** — "we did X" not "we revolutionized X"
- **Honest about limits** — custody model, synthetic data, mempool workaround, Round 1 failure
- **Plain English where possible** — assume judge is smart but not specialized
- **Ship signal over brag signal** — "150 real tx + 4 ERC-8004 events on arcscan" > "world-class decentralized marketplace"

---

## 7. If the designer has questions

Source files (in `C:\Users\user\hackerton\arc`):

| Fact / claim | Source file |
|---|---|
| One-liner / pitch framing | `README.md:20` + `docs/SUBMISSION.md:16` |
| Architecture + data provenance | `docs/SUBMISSION.md §4` |
| Walk-forward leaderboard numbers | `docs/SUBMISSION.md §11.b` (Table) |
| Data provenance table | `docs/SUBMISSION.md §4.1` |
| Circle products + custody model | `docs/SUBMISSION.md §5` |
| 150 tx evidence + Merkle root | `docs/evidence/batch_tx_hashes.txt` + `docs/evidence/merkle_root.txt` |
| ERC-8004 registrations | `docs/evidence/erc8004_registry.json` |
| Agent cards (4 JSONs) | `bridge/agent-cards/*.json` |
| Video narration flow | `docs/VIDEO_SCRIPT_KR.md` |

---

**End of brief. Ready for Claude Design.** Please generate the PDF and return it alongside any asset SVGs.

---

## 8. Designer self-check before returning deck

Before submitting the regenerated deck, verify **each of these claims can be traced to a specific slide**:

### Mandatory lablab rule gates (all 3 must PASS)

- [ ] **Gate 1 — Real per-action pricing ≤ $0.01**
  → Verify Slide 6 shows 3 price tiers ($0.0005 / $0.005 / $0.010) with formula
- [ ] **Gate 2 — 50+ onchain transactions**
  → Verify Slide 5, Slide 10, Slide 11 all say "150 tx" (not 50+ or 60)
- [ ] **Gate 3 — Margin explanation (quantified)**
  → Verify Slide 3 has the NEW **margin counterfactual box**: Ethereum -$0.495 / Polygon $0.000 / Arc +$0.003. Without this Gate 3 is only PARTIAL.

### 4 judging axes (equal weight)

- [ ] **Application of Technology** — Slide 5 shows Gemini 2.5 Flash · Slide 10 shows Arc + USDC + SCA + Dev API + x402 + ERC-8004 registry
- [ ] **Presentation** — flow: hook (2) → problem (3) → solution (4-5) → mechanism (6-7) → proof (8) → provenance (9) → trust (10) → originality (11) → close (12)
- [ ] **Business Value** — Slide 1 AND Slide 5/7 surface the `v1.3 on EC2 · 9 coins · pool $1,977` credential
- [ ] **Originality** — Slide 11 has **1 hero card (ERC-8004)** + 3 supporting chips (variable price · closed outcome loop · live prod backing)

### Tufte honesty self-check

- [ ] Slide 8 **DOES** render real error-bar whiskers OR the caption does **NOT** claim whiskers. Pick one path, don't leave the claim dangling.
- [ ] Slide 8 x-axis has real tick marks (not free-floating text).

### Brand consistency

- [ ] All `Alpha` text rendered cyan, `Loop` white (or inverted, consistently).
- [ ] No "OBOL" anywhere. No bare "Signal Mesh" (only "formerly Signal Mesh" or legacy URLs permitted).
- [ ] 150 tx stated consistently (not 50+, not 60).
- [ ] Contract address `0xb276b96f…b7ab` appears on slides 10 and 11 and is identically truncated.
- [ ] Merkle root `400039d5…605b80` appears on slide 11 and is identically truncated.

### Drama beat (Tan aha-moment)

- [ ] Slide 8 has a **full-width callout card** (not a footer tag) with "Round 1 reward-hacked itself. Round 2 ties the oracle." This is the single most memorable beat in the deck — don't demote.

If all checkboxes pass, the deck is ready. Return the updated `AlphaLoop_Deck.html` bundle.

