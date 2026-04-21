# Capital Allocator RL — Design Doc

**Status:** Draft v1 (Architect phase, F0). For Builder agents to implement in F2–F6.
**Cadence:** **8 hours** (aligned with Binance perp funding cycle — see §0 rationale).
**Author perspective:** Sutton/Barto-primary, cross-checked against Overdeck (target leakage), Griffin (adverse selection), Kelly (sizing).

---

## 0. Mandate & cadence rationale

The hackathon novelty claim is reduced to a single axis: **tabular Q-learning picks which of three orthogonal arb strategies gets capital, on an 8-hour cadence, conditioned on regime features.** The retired "Q-for-pricing-multiplier" claim is demoted to a supporting feature of the executor persona (it still runs, but is no longer the headline).

**Why 8h, not 6h:** 8h aligns exactly with Binance perpetual funding cycle (00:00 / 08:00 / 16:00 UTC). Each tick contains exactly one funding payment for v3 → clean reward attribution (no fractional cycle splitting), and v3 OPEN/CLOSE decisions naturally happen at funding boundaries. Sample budget cost: 25% fewer ticks/day vs 6h, mitigated by bootstrap (§4.5).

Three producers:

| id | Strategy | File-of-record | Hold horizon | Regime it thrives in |
|---|---|---|---|---|
| `v1_kimchi` | Upbit KRW ↔ Binance USDT | `v1_kimchi_premium/src/strategy/signal.py` | minutes–hours | KRW FOMO / bull |
| `v2_dual_quote` | Binance intra-venue USDT↔USDC | `v2_dual_quote_arb/src/v12/allocator.py` | seconds | microstructure (flat/chop) |
| `v3_funding` | Spot-long + perp-short funding capture | `v3_funding_rate/src/funding_strategy.py` | 8h–72h | sustained bull, positive funding |

The allocator does NOT decide entry timing (each producer keeps scanning continuously). It decides what fraction of available capital each producer is permitted to use over the next 8h.

---

## 1. State Space

**Shipped state: 2×2×2 = 8 cells, plus 1 "unknown/cold" sentinel = 9.**

| Feature | Buckets | Boundaries | Rationale |
|---|---|---|---|
| `vol_regime` | 2 (calm/hot) | BTC 8h realized σ; split at the 65th percentile of a 90-day rolling window (adaptive) | Binary split with rock-solid labeling beats a 3-way split with ambiguous middle. Non-stationarity mitigated by rolling percentile |
| `funding_regime` | 2 (cold/hot) | Median of top-10 perps funding at the most recent 8h tick; split at 0.01% (annualized ≈ 11%) | Decisive for v3; below this v3 cannot cover fees in 8h |
| `dislocation_regime` | 2 (tight/wide) | OR of `kimchi_premium ≥ 0.5%` OR `USDT-USDC cross-venue spread ≥ 8bp` | Compresses two co-moving features into one bit |

Plus a `cold` sentinel returned when any feature is missing. `cold` deterministically routes to a uniform prior allocation.

Why 9 cells beats 36:
- 270 pretrain ticks (90d × 3) ÷ 9 cells = 30 visits/cell vs 7.5 at 36 cells.
- Every cell label is human-readable; the demo heatmap is interpretable in 3 seconds.

**Feature sources** (implementation):
- `vol_regime`: BTC 1m parquet from v2's archive. Live: Binance WS optional.
- `funding_regime`: v3 already polls Binance `fapi/v1/premiumIndex`. Wrap into `ml/funding_features.py`.
- `dislocation_regime`: `kimchi_premium` from kimchi_agent stream; USDT-USDC spread from dual_quote_agent stream. No new dependency.

**Single source of truth:** `ml/regime_features.py::state_index(vol, funding, kimchi, usdc) -> int` returning 0..8. Used identically in pretrain and live (do NOT duplicate as `pretrain_q.py::sample_realized_edge` did — there was a deliberate-copy reason for that, but feature mapping has no stochasticity so a shared import is correct here).

---

## 2. Action Space

### 2.1 Discretization — shipped: 7 cells

| idx | v1 | v2 | v3 | label | Rationale |
|---|---|---|---|---|---|
| 0 | 1.0 | 0.0 | 0.0 | `ALL_V1` | Corner — "kimchi dominates in KRW FOMO" |
| 1 | 0.0 | 1.0 | 0.0 | `ALL_V2` | Corner — "dual-quote dominates in chop" |
| 2 | 0.0 | 0.0 | 1.0 | `ALL_V3` | Corner — "funding dominates in bull+hot-funding" |
| 3 | 0.5 | 0.5 | 0.0 | `KIMCHI_DUAL` | Edge — funding cold, dislocation present |
| 4 | 0.0 | 0.5 | 0.5 | `DUAL_FUND` | Edge — tight dislocation, hot funding |
| 5 | 0.5 | 0.0 | 0.5 | `KIMCHI_FUND` | Edge — wide dislocation + hot funding |
| 6 | 1/3 | 1/3 | 1/3 | `DIVERSIFY` | Centroid — "I don't know" + cold-state default |

**Excluded:** finer mixes (sample budget); ZERO action (allocator is never permitted to "hide" — `cold` routes to DIVERSIFY).

### 2.2 Action masking (applied BEFORE UCB1)

- **Safety mask:** if a strategy's trailing-72h NetPnL < −2σ of its 90-day distribution, remove actions placing >50% on it. Always keep at least one action (fallback: DIVERSIFY).
- **Capability mask:** `funding_regime == cold` → mask `ALL_V3`. Domain constraint, not learned.

---

## 3. Reward

### 3.1 Signal

Per 8h tick, for each strategy `s ∈ {v1, v2, v3}` measure realized NetPnL `pnl_s`. Aggregate reward for selected allocation `w`:

```
raw_reward = Σ_s w_s × pnl_s
```

This is attributed reward (not portfolio total) — credits the chosen action, not ambient market.

### 3.2 Normalization — z-score per strategy + dollar tiebreaker

Three strategies emit different distributions (kimchi sparse $0.5–$5, dual continuous $0.01–$0.50, funding $0.05–$2 per 8h on $500). Raw dollars would let kimchi crush the table on rare hits (Overdeck target-distribution-mismatch). Sharpe-online would be too noisy with thin samples.

**Shipped:**

```
μ_s, σ_s = pretrain_distribution(s)   # frozen after pretrain
z_component = Σ_s w_s × (pnl_s − μ_s) / σ_s
dollar_component = Σ_s w_s × pnl_s / DOLLAR_SCALE
reward = (1 − λ) × z_component + λ × dollar_component
```

`λ = 0.2`, `DOLLAR_SCALE` calibrated from pretrain (75th-percentile of best-performing strategy's 8h PnL, ≈ $2). **F8-fix (Overdeck):** `μ_s, σ_s, DOLLAR_SCALE` are calibrated on a held-out **60-day window (2026-01-21 → 2026-03-22)** and then frozen; the remaining **30 days (2026-03-22 → 2026-04-21)** are used for Q-table training with the frozen constants. Prevents in-sample reward normalization leakage — a Two-Sigma-grade check that pretrain distribution ≠ train distribution.

### 3.3 Target-leakage audit (Overdeck)

Three potential leaks; all blocked:

1. ❌ **Using realized `pnl_s` as a state feature for next tick.** Rejected — state features are computed from market data only, never from our own PnL.
2. ❌ **Using volatility from `[t, t+1)` for state at t.** Rejected by construction — feature windows are `[t−8h, t)` (trailing).
3. ⚠️ **Reward function accidentally taking state features.** Mitigation: `reward_fn(action, pnl_v1, pnl_v2, pnl_v3)` signature only. State features go to Q-update, never to reward.

---

## 4. Pretrain Pipeline

### 4.1 Data coverage — reality check

Plan agent confirmed during F0:

| Path | Reality |
|---|---|
| `v2_dual_quote_arb/data/backtest/1s/*20260419.parquet` | **One day** of 1s bars across 48 symbols. Not 6 months. |
| `v2_dual_quote_arb/data/live_trades/*.csv` | 20260411–20260412 multi-day live trade logs |
| `v1_kimchi_premium/data/...` | **Does not exist** at expected path — locate or backfill via Upbit+Binance public REST |
| `v3_funding_rate/data/...` | **Does not exist** — backfill 90d from Binance `fapi/v1/fundingRate` (public REST, no key needed) |

**F1 (data coverage explore) must resolve before F5 builds.** Builder must NOT assume 6 months.

**Minimum viable pretrain:** 90 days × 3 ticks/day = **270 real ticks**. At 9 states × 7 actions = 63 cells, ≈ 4.3 visits/cell — thin. Bootstrap to ~1500 by resampling within-regime (preserves autocorrelation honestly).

### 4.2 Offline replay loop (in `scripts/pretrain_allocator_q.py`)

```python
# pseudocode
for t in tick_timeline:
    state_t = regime_features.state_index(vol[t], funding[t], kimchi[t], usdc[t])
    # Enumerate all actions per tick — counterfactual data is free at pretrain time
    for action_idx in range(NUM_ACTIONS):
        w = ACTIONS[action_idx]
        r = reward_fn(w, pnl_v1[t], pnl_v2[t], pnl_v3[t])
        policy.update(state_t, action_idx, r, accepted=True)
```

### 4.3 Why enumerate (Sutton/Barto sample-efficiency)

At pretrain, we know `(pnl_v1, pnl_v2, pnl_v3)` for every tick — the full counterfactual. Enumerating across all 7 actions per tick gives us 7× the samples vs on-policy rollout. Q-learning is off-policy so this is sound.

**Live time only updates the chosen action** — must be documented so the SUBMISSION doesn't overclaim.

### 4.4 Exploration & init

- UCB1 (`UCB_C = 0.5`) — matches `pricing_policy.py`.
- Optimistic init `Q_INIT = 0.5` — calibrated vs z-scored reward range (σ≈1, so Q₀ = 0.5σ gives each unvisited action a meaningful optimistic lead that survives ~5 visits of below-average reward before collapsing). **F8-fix:** raised from 0.05 after Giants' Shoulders review showed 0.05 was ~15× smaller than the z-reward std and collapsed UCB optimism within 1-2 visits.
- No ε-greedy.

### 4.5 Hyperparameters

```
ALPHA = 0.1
Q_INIT = 0.5          # F8-fix: raised from 0.05 to match z-reward scale
UCB_C = 0.5
NUM_STATES = 9          # 8 regime cells + 1 cold sentinel
NUM_ACTIONS = 7
PRETRAIN_TICKS = 270    # 90d × 3 ticks/day, real
BOOTSTRAP_RESAMPLES = 1500
HOLD_SEC = 28800        # 8h, prod
DEMO_HOLD_SEC = 30      # demo override only — features still computed over trailing 8h
```

---

## 5. Safety Rails

### 5.1 All-negative tick sequence
**Scenario:** rolling 24h `raw_reward` < −2.0 (z-units).
**Rail:** freeze Q-table for 12h, publish `allocation_frozen: true`. Resume when rolling reward returns above −0.5. Dashboard shows freeze state.

### 5.2 Regime distribution shift (Kelly)
**Scenario:** strategy's online `μ_live` drifts > 1σ from pretrain `μ_pretrain` for 2 weeks.
**Rail:** halve that strategy's weight in any mixed action (`drift_downsize: {v1: 0.5, ...}`). Runtime scaling, not Q-update. Surfaced on `/allocation`.

### 5.3 Producer outage (Griffin)
**Scenario:** producer hasn't reported `/strategy/tick_pnl` in > 16h (2× expected).
**Rail:** treat reward contribution as `μ_s` (prior mean), not zero. Avoids "silent producer looks safe" failure.

### 5.4 Mask degenerate
If safety + capability masks eliminate all 7 actions, fall back to `DIVERSIFY` and log `SAFETY_MASK_DEGENERATE`. Dashboard shows warning badge.

### 5.5 Dollar drawdown rail (F8-fix, Kelly)
**Scenario:** cumulative NetPnL since pretrain boundary crosses −8% of starting book.
**Rail:** freeze allocator (set `allocation_frozen: true, frozen_reason: "DRAWDOWN_RAIL"`), route to `DIVERSIFY` with 0.33× notional scalar, require manual unfreeze. Why: the §5.1 z-score rail normalizes out sustained bleed — it fires only on *anomalously* bad ticks, not on consistent-but-modest drain. Dollar rail is the explicit ruin-prevention floor that Kelly's original derivation assumes exists.

### 5.6 Griffin crowding at funding boundary — RESOLVED (option A)
**Problem:** v3 entry at exactly 00:00/08:00/16:00 UTC funding print is the single most crowded moment in crypto. Basis widens adversely in the ±2min window around print as every funding-farmer books size. Executing at print = eating the crowd cost.

**Shipped mitigation (user decision 2026-04-21):** v3 entry is deferred **+3 minutes** past each allocator tick boundary. Rationale: by T+3min the front-running pressure has dissipated and basis typically snaps back toward fair; the funding payment itself has already settled at T+0, so the 3-minute delay does not cost a cycle.

**Implementation contract:**
- Allocator `/allocation` payload gains a `v3_entry_offset_sec: 180` field (fixed constant in v1; promoted to policy output in a future iteration).
- Executor, when opening a v3 position in response to an allocation tick at T, schedules the OPEN call for `T + 180s`. For allocations where `weights.v3 == 0`, the offset is ignored.
- v2 and v1 have offset 0 (their alpha decay is too fast to defer).
- Demo mode (`--allocator-tick-seconds 30`): offset scales to `ceil(3 * (30/28800))` ≈ 0s; the +3min is a prod-cadence construct only. Dashboard shows "v3 entry offset: +3min (prod) / 0s (demo)" disclosure.

**Why not option B** (downweight ALL_V3 in hot funding): would mask a structural execution problem inside the policy and confuse the Q-table's regime-action attribution. Option A keeps the policy clean and moves the fix to the execution layer where it belongs — classic Griffin "execution edge, not alpha edge" framing.

---

## 6. Pre-Mortem

### F-ALLOC-1 — Forward-looking state features (Overdeck)
**Failure:** vol/funding/kimchi/usdc accidentally computed over `[t, t+8h)` instead of `[t−8h, t)`.
**Mitigation:** `regime_features.py` API takes `reference_timestamp` and asserts all feature windows ≤ `tick_start`. Unit test fires on shifted tick.

### F-ALLOC-2 — Sample starvation (Sutton/Barto)
**Failure:** 270 / 63 ≈ 4.3 visits/cell. UCB1 with optimistic Q0 lets first-visited action win each cell; calendar order biases first visits.
**Mitigation:** (a) shuffle pretrain tick order; (b) enumerate all actions per tick (§4.3) → ≈30 visits/cell post-enumeration; (c) bootstrap to 1500 within-regime.

### F-ALLOC-3 — Pretrain ↔ live regime non-stationarity (Sutton/Barto)
**Failure:** demo regime not represented in pretrain. ALPHA=0.1 too slow to recover in 90s.
**Mitigation:** (a) adaptive percentile vol bucket; (b) `cold` sentinel → DIVERSIFY for novel regimes; (c) SUBMISSION explicitly states demo exercises the PRIOR.

### F-ALLOC-4 — Hardcoded reward constants before data (Overdeck target def)
**Failure:** specifying `λ=0.2`, `DOLLAR_SCALE=$2` before pretrain reveals actual distributions risks double-rewarding the dominant strategy.
**Mitigation:** Builder computes `μ_s, σ_s, DOLLAR_SCALE` as OUTPUTS of pretrain pass 1. Re-runs Q-table pretrain in pass 2 with calibrated constants.

### F-ALLOC-5 — Demo invisibility (Griffin — bet doesn't pay inside window)
**Failure:** 8h cadence × 90s demo = 0 ticks. Allocator looks static.
**Mitigation:** see §8.

### F-ALLOC-6 — Credit assignment collapse to DIVERSIFY (Sutton/Barto)
**Failure:** DIVERSIFY's low-variance lightly-positive z-reward dominates short pretrain. Heatmap turns solid-DIVERSIFY.
**Mitigation:** `Q_INIT` applied UNIFORMLY across all 7 actions. **Verification gate:** ≥3/9 state cells must converge to a corner action; otherwise pretrain is rerun with more bootstrap.

### F-ALLOC-7 — v3 partial-cycle credit (Griffin) — RESOLVED BY 8h CADENCE
**Why removed:** the user-directed 8h cadence aligns each tick with exactly one funding payment. v3 reward at tick t is simply `funding_rate(t) × notional` minus accrued mark-to-market over the tick. No fractional-cycle splitting needed, no `cashflow_component` vs `mtm_component` accounting. The reward function for v3 is:

```
pnl_v3(t) = (funding_received_at_8h_mark[t]) + (basis_change[t])
          − (entry_fees if opened in this tick else 0)
          − (exit_fees if closed in this tick else 0)
```

Single line, no time-window arithmetic. This is the cleanest single benefit of the 8h cadence over 6h.

---

## 7. Interface Contract

### 7.1 New bridge endpoints (F4)

```
POST /allocation             — allocator consumer publishes its current decision
GET  /allocation             — dashboard + executor poll
GET  /allocation/history     — last N ticks for the Policy Heatmap card
POST /strategy/tick_pnl      — each producer reports per-8h NetPnL
```

### 7.2 Payload schema

```json
{
  "tick_id": "2026-04-21T08:00:00Z",
  "weights": { "v1_kimchi": 0.5, "v2_dual_quote": 0.0, "v3_funding": 0.5 },
  "action_idx": 5,
  "action_label": "KIMCHI_FUND",
  "state_idx": 6,
  "state_label": "hot-vol/hot-fund/wide-disloc",
  "regime_features": {
    "vol": 0.042,
    "funding_median": 0.00018,
    "kimchi_premium": 0.011,
    "usdc_spread": 0.0004
  },
  "q_value": 1.23,
  "q_value_second_best": 0.88,
  "exploration_bonus": 0.14,
  "ucb_score": 1.37,
  "drift_downsize": { "v1_kimchi": 1.0, "v2_dual_quote": 1.0, "v3_funding": 1.0 },
  "allocation_frozen": false,
  "frozen_reason": null,
  "updated_at": 1713657600,
  "next_tick_at": 1713686400,
  "cadence_seconds": 28800,
  "pretrained": true
}
```

`q_value_second_best` + `exploration_bonus` let the dashboard show *why* this action was picked — the Karpathy-school defense against "is RL decoration?".

### 7.3 Executor integration

Before this change: `consumers/executor_agent/main.py` opens a paper position per signal, regardless of strategy.

After:
1. At each loop iteration executor fetches `/allocation.weights`.
2. Signal arrives from producer `s` → `size_usd = base_notional × weights[s]`.
3. If `weights[s] == 0`, executor STILL pays for the signal (marketplace economics intact) but opens **zero-size paper position**. Tagged `allocator-muted` on dashboard.
4. Outcome posted as `notional_usd=0` → `pnl_usd=0`. Doesn't pollute allocator's reward (which reads from `/strategy/tick_pnl`, not `/signals/outcome`).

Clean separation: executor decides "how much through THIS signal"; allocator decides "what fraction of book each strategy gets"; multiply.

### 7.4 Allocator reward source (no circular dep)

Allocator does NOT consume `/signals/outcome`. Each producer posts `POST /strategy/tick_pnl` every 8h:

```json
{
  "producer_id": "v3_funding",
  "tick_end": "2026-04-21T08:00:00Z",
  "cashflow_usd": 1.24,
  "trades": 2
}
```

Keeps the reward signal clean from executor-side noise (paper-trade variance, signal price paid, etc.).

---

## 8. Hackathon demo risks

### 8.1 Invisibility — mitigation
- `--allocator-tick-seconds 30` CLI override (default 28800 = 8h prod). Decision cadence ONLY — feature windows still trailing 8h.
- Dashboard `AllocatorCard` shows "demo cadence: 30s (prod: 8h)" badge — pre-empts "this is faked".
- Pre-roll: run allocator over pretrain data at 5× speed BEFORE demo to fill `/allocation/history` with ~30 realistic ticks. Live demo adds ~3 ticks; heatmap appears warm.

### 8.2 Pretrain doesn't converge
F-ALLOC-6 verification gate must pass before demo (≥3/9 cells corner action). If fails, raise alert + tune `Q_INIT`/`UCB_C`.

### 8.3 Live data outage
WS drop → `funding_regime=missing` → `cold` sentinel → DIVERSIFY. Dashboard shows `cold` badge. Story becomes "graceful degradation" not "crash".

### 8.4 v3 producer doesn't exist yet
F2 MUST land before F3. Wrapper can be minimal — wraps `funding_strategy.should_enter`/`should_exit` and posts `/strategy/tick_pnl`.

### 8.5 Two Q-tables (pricing vs allocator) confusing the judge
SUBMISSION reframes pricing Q as "persona-aware operational fee recovery"; allocator is THE RL agent. F7 task handles the rewrite.

### 8.6 Demo override = cheating?
`--allocator-tick-seconds N` ONLY changes decision cadence. Feature windows ALWAYS trailing 8h. Documented in script and code.

---

## 9. Implementation sequencing

1. **F2** — v3 funding → arc producer wrapper. Posts `/strategy/tick_pnl`.
2. **F4a** — bridge: `/allocation`, `/allocation/history`, `/strategy/tick_pnl` endpoints.
3. **`ml/regime_features.py`** — single-source state encoder. Unit test for F-ALLOC-1.
4. **F1** — data coverage realization. Confirm or backfill v1/v2/v3 data.
5. **F5** — `scripts/pretrain_allocator_q.py`. 270-tick enumerated replay; calibrates `μ_s, σ_s, DOLLAR_SCALE`; emits `consumers/capital_allocator/allocator_q.json`. F-ALLOC-6 gate.
6. **F3** — `consumers/capital_allocator/main.py`. Online loop.
7. **Executor patch** — multiply notional by `weights[producer_id]`.
8. **F6** — dashboard `AllocatorCard` + `PolicyHeatmap`.
9. **F7** — SUBMISSION + VIDEO rewrite.
10. **F8** — Giants' Shoulders review pass.

---

## 10. Success criteria

- Pretrain: ≥3/9 state cells converge to a corner action (F-ALLOC-6).
- Live 90s demo with `--allocator-tick-seconds 30`: Policy Heatmap lights ≥3 distinct (state, action) cells.
- `/allocation` returns valid payload < 500ms.
- Executor: `notional_usd` correctly scales by `weights[producer_id]` — verified across 5 opens.
- Forced regime change (env override) shifts allocation within 2 ticks.
- SUBMISSION reframes pricing Q as operational; allocator as novelty; all three strategies credited as the portfolio being allocated over.

---

## Critical files for implementation

- `consumers/executor_agent/pricing_policy.py` — pattern reference for new allocator Q-table (state/action/UCB1/safety rail shape)
- `scripts/pretrain_q.py` — pattern reference for `pretrain_allocator_q.py` (enumerated replay, μ/σ calibration)
- `bridge/src/index.ts` — bridge to extend with `/allocation`, `/allocation/history`, `/strategy/tick_pnl`
- `consumers/executor_agent/main.py` — to patch with `weights[producer_id]` notional scaling
- `C:\Users\user\trading\arb\ai_agent_trading_v1.0\v3_funding_rate\src\funding_strategy.py` — v3 entry/exit semantics for F2 producer wrapper
