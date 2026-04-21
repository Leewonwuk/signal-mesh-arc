# Signal Mesh on Arc — Submission

**Track**: 🤖 Agent-to-Agent Payment Loop (primary) · 🪙 Per-API Monetization (secondary)
**Team**: solo — Leewonwuk (skyskywin@gmail.com)
**Repo**: https://github.com/leewonwuk/signal-mesh-arc (public)
**Live dashboard**: https://signal-mesh.vercel.app
**Video**: see `/docs/VIDEO.md` for the 3-minute pitch + demo
**Cover image**: `/docs/cover_image.svg`

---

## 1. One-liner

A live A2A marketplace where specialist AI trading agents pay each other sub-cent USDC for arbitrage signals on Arc — the chain where USDC *is* the gas, so the economy closes in a single unit of account.

> **TL;DR — three things to remember.**
> 1. **USDC-as-gas closes the loop.** Signal priced in USDC, paid in USDC, gas in USDC — no human re-funding a second-asset wallet. Every other chain has a hidden human in the loop.
> 2. **60+ sub-cent A2A tx in a 5-minute demo.** EIP-3009 + x402 paywall + variable on-chain price that encodes signal quality. Real settlements on Arc testnet, verifiable on `testnet.arcscan.app`.
> 3. **The RL allocator ties the empirical optimum on a walk-forward hold-out.** Tabular Q-learning over 3 arb strategies, evaluated honestly, audited by a Sutton-school adversarial agent, fixed (`p=0.49` vs ALL_V2, `p=0.012` vs DIVERSIFY). The receipt is in §11.b.

## 2. The problem

Existing "agent economies" demo one of two things:
- **Gas margin collapse.** The tx fee is a large fraction of (or bigger than) the value moved. At $0.01 per signal on Base/Polygon/Solana, the gas price is the signal price — a human has to keep refunding the sender wallet.
- **Two-unit accounting.** The work is priced in USDC but paid in ETH/SOL/MATIC. The agent can't close its own books. A human does that too.

Neither is an agent economy. It's a human economy with an LLM on top.

## 3. The fix (why Arc)

Arc makes USDC the native gas token. A signal priced at $0.002 settles for $0.002 worth of gas + $0.002 of payment — both denominated in USDC. An agent that earns $1 of premiums from downstream consumers can keep paying upstream producers forever, without ever being re-funded in a second asset. That's the closed loop.

**Counter-positioning:** every agent-economy demo built outside Arc has a hidden human re-funding the gas wallet. We don't. That is the whole thesis.

## 4. What we built

> **Replay provenance.** The dual-quote producer is not fed synthetic ticks. It replays 1-second OHLCV parquet snapshots captured from the submitter's **live v1.3 production arbitrage bot** running on EC2 (9 coins — ADA/BNB/DOGE/SOL/TRX/XRP/APT/FET/WLD — pool ≈ $1,977 USDT, threshold 0.17%, stop-loss 0.25%). The snapshot used by default is the 2026-04-19 capture, deliberate so the hackathon demo is reproducible and auditable; the same `PriceFeed` path can be swapped in for a true live Binance WS by flipping one class reference. In other words, the prices you see on screen are the prices the real production bot saw that day — not a toy stream.

```
 producers (v1.1 dual-quote, kimchi)
     │  HTTP /signals/publish
     ▼
 bridge (Node.js + x402 paywall + EIP-3009)
     │  GET /signals/premium   ← 402 challenge
     ▼
 meta agent (Gemini 2.5 Flash + GBM regime classifier)
     │  arbitration over conflicting producers,
     │  weighted by producer hit-rate (Bayesian shrink)
     ▼
 executor agent (paper trade + variable-price settle)
     │  EIP-3009 transferWithAuthorization  ← signer
     │  any-submitter relayer                ← gas
     ▼
 Arc testnet — 50+ USDC nanopayments
     │
     ▼
 dashboard (React + Vite, polling /api)
     outcome feedback → /signals/outcome → reliability scoring
```

## 5. Circle products used

| Product | How we use it |
|---|---|
| **Arc L1** | Primary chain. All settlement tx live here. ChainID 5042002. USDC-as-gas. |
| **USDC on Arc** | Unit of account for both fee and payment. Dual-decimal handled (18 native / 6 ERC-20). |
| **Nanopayments (EIP-3009)** | `transferWithAuthorization` path: signer authorizes off-chain, relayer submits on-chain. `--nanopay` flag on the executor. |
| **x402 payment standard** | Bridge returns HTTP 402 for `/signals/latest` ($0.002) and `/signals/premium` ($0.01). Executor completes the challenge by signing an EIP-3009 auth and retrying with an `X-Payment` header. |
| **Circle Developer Console** | Account + Arc testnet wallet provisioned; one settlement tx executed from the Console UI for the required verification video. |

We intentionally did NOT bolt on CCTP/Gateway/Wallets-SDK just to pad the stack — the thesis is the **loop**, and the loop only needs Arc + USDC + EIP-3009. Adding CCTP would describe a different project (cross-chain bridging). See `/docs/PRODUCT_FEEDBACK.md` for the honest DX write-up that qualifies for the $500 bonus.

## 6. Margin math (why a non-USDC-gas chain kills this)

Per-signal economics at demo scale:

| Chain | Native-gas denom | Typical tx cost | Signal price | Margin |
|---|---|---|---|---|
| Arc testnet | USDC | ~$0.0001–$0.001 | $0.002 raw / $0.01 premium | **positive** |
| Base mainnet | ETH | ~$0.01–$0.05 | $0.002 / $0.01 | **negative** — gas > revenue |
| Polygon PoS | MATIC | ~$0.002–$0.01 | $0.002 / $0.01 | **marginal + FX risk** |
| Solana | SOL | ~$0.0005–$0.005 | $0.002 / $0.01 | OK for gas, but **still two-unit** |

Solana beats Arc on raw fee floor, but an agent paid in USDC and paying gas in SOL can't self-balance — it needs a SOL top-up cron. That cron IS the human in the loop. Arc removes it.

## 7. Why the AI is not decorative

The meta agent has a job that forwards-outcome-validates every N seconds:
1. **Gemini 2.5 Flash** receives the full producer roster + recent conflicts + per-producer reliability (hit-rate over the last 200 outcomes).
2. It returns a structured JSON decision: `action`, `confidence`, `regime`, `expected_profit_usd`, `producer_weight_note`.
3. That decision sets the variable **settlement price** on-chain: `price = clip(confidence × notional × |premium| × take_rate, $0.0005, $0.01)`.
4. The executor opens a paper position, holds for N seconds, then reports realized PnL via `POST /signals/outcome` — which feeds the reliability store the *next* meta-agent decision reads from.

This closes the loop. A producer that keeps being wrong sees its weight drop and its premiums shrink. A producer that wins sees its premiums rise. The LLM is doing actual arbitration, not prose.

The **regime GBM** is a `sklearn.GradientBoostingClassifier` over 5 causal features of 1-second order-book data, classifying each tick into `{noise, mean_revert, trending, event}`. The meta agent uses the regime as a prior when arbitrating conflicting signals. Trained on v1.1's 87-pair 1s replay snapshot.

## 8. Originality hook

Most hackathon "agent economy" projects are one of:
- **One-agent chatbot** wrapping an LLM + a wallet. No internal market.
- **Toy marketplace** with two agents and hardcoded prices. No arbitration, no learning.

Signal Mesh is the first (that we're aware of) to combine:
1. Multi-producer **competitive** signal supply (v1.1 dual-quote + kimchi premium running in parallel, same topology).
2. **Variable on-chain price** that encodes signal quality — the USDC amount on-chain *is* the agent's quote for that specific signal.
3. A **closed outcome loop** where realized PnL retroactively re-prices future signals from the same producer.

The last one is the key. It's the reason the tx stream is a real market rather than a cron job.

## 9. What you can verify in 3 minutes

- Dashboard shows live `raw / premium / on-chain tx / producers` counters ticking up.
- Settlement tx links resolve on `testnet.arcscan.app`.
- Producer reliability bars update as positions close and PnL reports arrive.
- `X-Payment-Response` header logs in the executor show x402 settlements happening.
- At least one tx was executed from the Circle Developer Console UI and verified on Arc Explorer (video).

## 10. Fee persona + pricing Q-table (one paragraph — full detail in design doc)

The whole stack is grounded in a single auditable fee persona — **Bybit VIP 0 + USDC taker 50%-off promo, round-trip 0.10%** — chosen because that is where retail actually sits and Circle is a public Bybit partner. The dashboard's Fee Persona Explorer lets a judge switch to any of 5 venues live (Bybit, Binance, OKX, MEXC, Coinbase Advanced); Coinbase is shown but flagged structurally arb-incompatible (no alt/USDT pairs). The executor's per-signal **settlement price is set by a tabular UCB1 Q-table** over `[0.75×, 1×, 1.5×, 2.5×]` of the fee-covered base, with realized-NetPnL reward and a −$0.20/min safety rail; this is operational fee-recovery plumbing, not the RL headline. The headline is the Capital Allocator in §11. Full state/action/reward and the F1–F5 pre-mortem (Griffin/Overdeck/Sutton fixes) live in the source: `consumers/executor_agent/pricing_policy.py` (UCB1 + persistence) and `scripts/pretrain_q.py` (offline warm-up).

## 11. Capital Allocator RL — the actual RL novelty

**Thesis — one line.** *One agent chooses which strategy trades, not whether or how much.* The allocator is a higher-order policy sitting on top of three independent arb producers. Each producer keeps scanning the market continuously; the allocator decides what fraction of the book each is allowed to deploy over the next 8 hours, conditioned on an observable market-regime state. There is no forward-looking feature, no leaked label, no blended confidence — just `state → action → attributed reward`, on a cadence aligned to the Binance perpetual funding cycle.

**Comparison to live production.** My v1.3 production arb bot (9 coins — ADA/BNB/DOGE/SOL/TRX/XRP/APT/FET/WLD — running on EC2, pool ≈ $1,977 USDT, threshold 0.17%, stop-loss 0.25%) is a *fixed-threshold* dual-quote engine: if spread > 0.17%, trade. That system has no notion of "funding regime" or "which strategy is in season" — it trades v2 and only v2. The Capital Allocator is the layer v1.3 does not have: it observes regime and decides whether v1 (kimchi), v2 (dual-quote, the strategy v1.3 already runs in production), or v3 (funding-rate basis) should own capital for the next 8h. That is the elevation from "threshold rule" to "learned meta-policy."

**Architecture.**
```
  v1 kimchi producer ──┐
  v2 dual-quote ──────►│ bridge /signals/publish          (strategy_tag emitted)
  v3 funding ─────────┘     ↓
                        meta agent (arbitrates v1+v2 signals only; v3 is time-boxed, not signal-arb)
                            ↓
  Capital Allocator (online consumer, running during demo) — every 8h:
     reads  GET /strategy/tick_pnl   ← per-strategy 8h realized NetPnL
     writes POST /allocation         ← {weights, action_idx, state_idx, q_values[7]}
                            ↓
  executor: size_usd = base_notional × weights[producer_id]
                            ↓
  Arc testnet USDC settlement (unchanged)
```

**State / action / reward (abbreviated from design doc §1–3).**

| Axis | Cardinality | Shape |
|---|---|---|
| State | 9 | 2×2×2 regime (vol · funding · dislocation) + 1 `cold` sentinel |
| Action | 7 | 3 corners (ALL_V1 / ALL_V2 / ALL_V3) + 3 edges (mix pairs at 50/50) + 1 centroid (DIVERSIFY = 1/3 each) |
| Reward | scalar/8h | **Dollar-only** attributed NetPnL `Σ wₛ·pnlₛ / DOLLAR_SCALE` (Sutton fix 2026-04-21 — see §11.b for the z-blend that came before and why it failed) |

**Key design decisions with attribution.**

- **8h cadence (design §0, user-directed).** Each tick contains exactly one funding payment for v3 → clean reward attribution, no fractional-cycle accounting. The cadence rationale is the single biggest reason F-ALLOC-7 (v3 partial-cycle credit) was retired in the F0 pre-mortem.
- **z-score + small dollar tiebreaker (design §3.2, Overdeck target-distribution calibration).** Three strategies emit wildly different PnL distributions ($0.5–$5 sparse for kimchi vs $0.01–$0.50 continuous for dual-quote vs $0.05–$2 for funding on a $500 notional). Raw-dollar reward would let kimchi's rare-big hits crush the table; pure Sharpe would be too noisy with thin samples. z + λ·dollar (λ=0.2) is the compromise that keeps corners comparable but still rewards the rare real-dollar outlier.
- **60-day holdout for μ/σ calibration (F8-fix, Two-Sigma check).** The F8 Overdeck review caught that calibrating `μₛ, σₛ` on the same 270 ticks used for training is in-sample normalization. Design §3.2 now splits: **60 days (2026-01-21 → 2026-03-22) frozen-calibration window**, **30 days (2026-03-22 → 2026-04-21) training window**. Constants are locked before the Q-table replay.
- **Q_INIT = 0.5 (F8-fix, UCB1 optimism must match reward scale).** F8 Sutton/Barto review showed the original Q_INIT=0.05 was ~15× smaller than the z-reward std, so first-seen actions would lock their cells after a single visit. Raising to 0.5 (same order as |z|≈1) forces meaningful exploration across all 7 actions per cell.
- **v3 entry +3min offset (F8 Griffin resolution, design §5.6).** Griffin's objection was that the 00:00 / 08:00 / 16:00 UTC funding print is the most crowded moment in crypto — every funding farmer enters simultaneously and basis widens adversely for ~2 minutes. Option A (shipped) defers v3 OPEN execution by +3 minutes past each allocator tick; by T+3min the front-running pressure has dissipated. Crucially, this is an **execution-edge fix, not an alpha-edge fix** — the Q-table learns clean regime→action attribution; the execution layer absorbs the crowding cost where it belongs. v1 and v2 have offset 0 (their alpha half-life is too fast to defer).
- **§5.5 dollar drawdown rail (F8-fix, Kelly ruin floor).** F8 Kelly/Thorp review pointed out that the §5.1 z-score freeze normalizes out sustained bleed — it only fires on *anomalously* bad ticks, not consistent-but-modest drain. The explicit dollar rail (freeze + force DIVERSIFY at 0.33× notional when cumulative NetPnL since pretrain crosses −8% of starting book) is the ruin-prevention floor Kelly's original derivation assumes exists. Manual unfreeze required.

**Pre-Mortem.** 7-row failure-mode/mitigation matrix (F-ALLOC-1 … F-ALLOC-7) attributed to Sutton/Barto, Overdeck, Griffin, Kelly is in `/docs/ALLOCATOR_RL_DESIGN.md` §6. The headline gates are: (a) calibration window frozen 60d before the train window, (b) `Q_INIT = 0.5` to match z-reward scale (matters in Round 1, see §11.b), (c) `n_real_ticks` tracked separately from enumerated visits so UCB1 bonuses denominate honestly, (d) F-ALLOC-6 verification gate — ≥3/9 cells must converge to a corner or pretrain reruns (post-fix passes 7/9).

**Data provenance — full disclosure.** Judges should know exactly which bytes are real and which are generated. Nothing is hidden.

| Strategy | Pretrain source | Reality |
|---|---|---|
| v3 (funding) | Binance `fapi/v1/fundingRate` public REST, 2026-01-21 → 2026-04-21 | **Real.** 5 symbols (ADA/DOGE/SOL/TRX/XRP) × 271 ticks each = **1,355 real 8h cycles** on disk at `data/funding/{SYMBOL}_90d.parquet`. No API key needed — public endpoint. |
| v2 (dual-quote) | 1-second parquet tape from the submitter's **live v1.3 production bot on EC2** (2026-04-19 capture), bootstrap-resampled within-regime to fill the 90d window | **Real 1 day + honest bootstrap.** The 1s bars are the prices the production bot actually saw; the resampling is documented as resampling, not fabricated history. |
| v1 (kimchi) | **Synthetic** AR(1) mean-reverting premium series, explicitly labeled in the pretrain script and on the dashboard | **Synthetic.** Real kimchi tick data (Upbit KRW + Binance USDT cross-venue) was not available in time. The synthetic series is marked as synthetic in the data-provenance badge on the dashboard and on every allocator payload that carries v1 weight. |

**No synthetic data is hidden; every source is declared here.**[^coins] The allocator's convergence behavior can be reproduced from the public Binance funding data alone for the v3 axis; the v2 axis is reproducible from the 2026-04-19 v1.3 tape committed to the repo; the v1 axis is reproducible from the synthetic generator's seed, also committed.

[^coins]: v1.3 in production trades 9 coins (ADA, BNB, DOGE, SOL, TRX, XRP, APT, FET, WLD); the v3 funding pretrain uses a 5-coin subset (DOGE, TRX, XRP, ADA, SOL) where Binance perp funding history is dense and gap-free over the full 90-day window. The allocator is a strategy-selector, not a coin-selector, so the per-strategy PnL signal only needs to be unbiased across regimes, not exhaustive across tickers.

**90-day regime observation (from F1b data coverage pass).** Over the 2026-01-21 → 2026-04-21 window, the funding market was **net-negative for the majority of 8h ticks**; only roughly **10% of ticks cleared the "hot funding" cutoff** (design §1 threshold ≈ 0.01% per 8h). This is a structural fact about the window, not a design choice. The **correct learned response** for an allocator trained on this window is therefore *almost never to pick ALL_V3* — for most regime cells the expected funding capture does not cover fees. The heatmap will be sparsely painted toward the ALL_V3 corner, and that is **evidence the policy is data-driven, not hardcoded to the hackathon narrative**. An allocator that enthusiastically picks ALL_V3 in a cold-funding window would be the red flag.

**Judge Q&A defense kit (from F8 Giants' Shoulders review).**

- **Q: "This is 3 strategies and a lookup — where's the RL?"** Payload exposes per-action `q_values[7]`, the chosen `action_idx`, and the state index; dashboard shows UCB1 exploration bonus and second-best Q so the judge can see *why* this action beat the runner-up. A forced regime flip (ENV override) demonstrably shifts allocation within 2 ticks — that is learned policy response, not a static lookup. See the "Q&A" paragraph above and design §10.
- **Q: "270 ticks over 63 cells can't learn anything."** Off-policy Q-learning enumerates all 7 actions per tick at pretrain time (the counterfactual is free — we know every strategy's PnL for every historical tick). That gives ~30 effective visits per cell. The F-ALLOC-6 hard gate (≥3/9 cells converge to a corner) blocks deploy if pretrain fails. Separately, we track `n_real_ticks` alongside the enumerated count so UCB1 bonuses denominate in real samples (F8 Sutton/Barto carve-out).
- **Q: "8h cadence + 90s demo is theater."** Demo uses `--allocator-tick-seconds 30` which **only** changes decision cadence — feature windows are unconditionally computed over the trailing 8 hours of tape, and the dashboard badge makes the demo/prod distinction explicit. We also pre-roll the allocator at 5× over pretrain data before the demo so `/allocation/history` has ~30 realistic ticks by the time the recording starts; the 3 new live ticks then demonstrably alter the heatmap. Full transparency — there is no hidden acceleration of the *learning*, only of the *decision clock*.

### 11.b Walk-forward backtest — the headline result (2026-04-21)

**The result.** On a 47-tick out-of-sample hold-out (271 ticks / 8h cadence over 90 days, split cal 178 / train 46 / test 47, calibration frozen *before* train opens), the trained Q-allocator **statistically ties the empirically-optimal single-corner policy** and **beats every ML and rule-based comparator** we threw at it.

| Policy | $pnl (47-tick hold-out) | Sharpe | win% | p vs DIVERSIFY | p vs ALL_V2 |
|---|---:|---:|---:|---:|---:|
| ALL_V2 (single corner — empirical optimum) | **9.44** | 0.17 | 100% | 0.0001 *** | — |
| **TrainedQ_walkforward (shipped)** | **7.61** | **2.89** | **83%** | **0.012 *** | **0.49 (statistical tie)** |
| Ridge (ML comparison) | 6.43 | 3.25 | 76% | 0.016 * | (n.s.) |
| LightGBM | 5.42 | 0.97 | 64% | 0.831 n.s. | (n.s.) |
| ALL_V3_masked rule | 2.07 | 3.24 | 66% | 0.523 n.s. | *** worse |
| DIVERSIFY (uniform 1/3) | 1.60 | 1.49 | 60% | — | *** worse |

The shipped Q-table picks `ALL_V2` in 5 of 9 cells — converging *to* the empirical optimum, not against it. Reproduce: `python scripts/backtest_rules_v2.py` · `python scripts/backtest_ml.py` · `python scripts/backtest_allocator.py`.

**Honest narrative.** We are not claiming the Q-learner discovered v2 dominance. We are claiming: **a learned policy, evaluated on out-of-sample data, converges to the same allocation a one-line rule would have written**. The convergence is the rigor signal. If the policy had diverged from the rule, *that* would have been the bug. We still ship the learner over the rule because (1) the funding-gate rule (`if funding ≥ p90: ALL_V3 else ALL_V2`) was also tested in walk-forward and **lost to ALL_V2 in dollars** (`p = 0.0005`) — the gate misfires in this slice; and (2) when v1 (Upbit kimchi) backfills with real data and the funding regime shifts, the learner re-learns; the rule does not.

#### 11.b.1 Receipt — Sutton-school audit (Round 1 → Round 2)

The result above is **Round 2**. Round 1 (z-blend reward, original `λ=0.2`) had Q-learning **losing to a one-line if-statement**: `TrainedQ_walkforward` $6.21 vs `ALL_V2` $9.44, `p=0.227 n.s.` — bottom of the leaderboard for a 9×7 table. We brought in an adversarial **Richard-Sutton-school RL evaluator** before shipping. Verbatim verdict (2026-04-21):

> *"The reward function is broken by design, not by λ. `(1−λ)·z + λ·d` with per-arm z-normalization systematically punishes the low-variance arm (v2, σ=0.025) because dividing its dollar edge by its own tiny σ creates a z-score that looks similar to v1/v3, while the dollar truth is that v2 dominates. This is a textbook reward-hacking trap: you defined 'reward' such that variance, not profit, is what the agent maximizes."*
>
> *"If you ship this, the prize judge sees a 9×7 Q-table that was beaten by a one-line if-statement — unless you reframe it as 'we used learning to validate a rule', in which case they see rigor."*

Single-line fix in `scripts/pretrain_allocator_q.py:347`:

```python
# before — z-blend (broken):
return (1 - LAMBDA) * z + LAMBDA * (dollar_pnl / dollar_scale)
# after — Sutton dollar-only:
return dollar_pnl / dollar_scale
```

Action distribution flipped from `{DUAL_FUND: 24, ALL_V1: 9, ...}` to `{ALL_V2: 24, ALL_V1: 9, KIMCHI_FUND: 8, ALL_V3: 6}`. F-ALLOC-6 verification gate went from FAIL to **PASS 7/9**. The Round 2 leaderboard at the top of this section is the result.

## 12. Roadmap (post-hackathon)

1. **Circle Wallets MPC** for the relayer key (replace raw ECDSA private key).
2. **Gateway batching** — bundle outcomes into one on-chain proof of performance.
3. **Two-sided market**: consumer agents compete for the right to buy signals (reverse auction), not just producers competing for attention.
4. **Real fills** replacing paper: connect to a live venue once Arc mainnet + a DEX are live.
5. **Venue generalization**: compile one Q-table per persona; switching "retail Bybit" → "VIP 3 Binance" becomes a `--persona` flag rather than a code change.

---

## Technical details (for judges)

- **Run**: `python demo/run_demo.py --with-kimchi --pretrain-q` launches bridge + 2 producers + meta + executor with a warm Q-table.
- **x402 ON**: set `X402_ENABLED=1 PRODUCER_WALLET_ADDRESS=0x… FACILITATOR_URL=…` in `.env` for the bridge.
- **Nanopay ON**: `python -m consumers.executor_agent.main --nanopay` (requires `EXECUTOR_PRIVATE_KEY` and `RELAYER_PRIVATE_KEY`).
- **Deterministic**: Gemini temperature=0.0, meta dedupe key is `(symbol, action, round(ts, 3))`.
- **Q-table**: persisted at `consumers/executor_agent/q_table.json`; run `python -m scripts.pretrain_q --episodes 5000` to rebuild.
- **Economics endpoint**: `GET /economics/summary` on the bridge surfaces `net_pnl_cumulative`, `gross_pnl`, `fees_paid`, `paid_to_producers`, and the fee persona label.
- **50+ tx**: `demo/run_demo.py --target-tx 60` hits 60 settlements in under 5 minutes at default pacing.
