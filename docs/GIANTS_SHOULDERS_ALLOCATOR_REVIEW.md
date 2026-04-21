# Giants' Shoulders Review — Capital Allocator RL

**Subject:** `docs/ALLOCATOR_RL_DESIGN.md` (Draft v1, F0)
**Reviewer posture:** adversarial, 5 masters
**Reference:** existing `consumers/executor_agent/pricing_policy.py`

---

## Verdict table

| Master | Verdict | Headline |
|---|---|---|
| Sutton/Barto | **WARN** | UCB1 + Q_INIT=0.05 is fine, but 7-action enumeration inflates effective visits while credit assignment still rests on 30 true ticks/cell |
| Overdeck | **WARN** | Feature windows are clean, but `μ_s, σ_s` calibrated on pretrain then frozen = in-sample reward normalization |
| Griffin | **FAIL** | 8h cadence is a poor fit for v1 kimchi (minutes) and crowded for v3 funding (00:00 UTC print) |
| Kelly/Thorp | **WARN** | 3 of 7 actions are corners (all-in). No documented per-tick capital-at-risk cap |
| Renaissance | **WARN** | v2 basis and v3 funding both proxy USDT stress; correlation not audited. Cutoffs mostly adaptive, acceptable |

---

## 1. Sutton/Barto — RL correctness — **WARN**

**Flaw A (§4.3, §4.5):** Enumerated counterfactual replay gives 7× update count but the same 270 underlying ticks. `n_visits` appears healthy (~30/cell) but the *independent information* per cell is still ~4. UCB1 exploration bonus `sqrt(log N / n)` will shrink too fast because `N` is inflated, triggering premature greediness.
**Fix:** track a separate `n_real_ticks` counter; compute UCB bonus off real ticks, not enumeration count.

**Flaw B (§4.4 + §3.2):** Q_INIT=0.05 is stated as "slightly higher because reward is z-scored ~[−3, +3]." That's **15× smaller** than the reward range — first-seen action with even a modest positive z will blow past Q_INIT and lock the cell before other actions are tried. Pricing's 0.01 vs dollar rewards ≈$0.10 was the same ratio; here it's worse because z-scores are wider-tailed.
**Fix:** raise `Q_INIT` to ~0.5 (same order as typical `|z|≈1`) so optimistic init actually forces exploration across all 7 actions per cell.

## 2. Overdeck — target leakage & skew — **WARN**

**Flaw A (§3.2):** `μ_s, σ_s, DOLLAR_SCALE` are computed on the 270-tick pretrain set *and then frozen for the second pretrain pass on the same 270 ticks*. That is **in-sample normalization** — the reward in pass 2 is deflated exactly by pass-1 dispersion, artificially inflating corner Q-values for strategies with tight pretrain dispersion. This is the Overdeck "target definition uses the same sample" failure, just moved from features to reward.
**Fix:** compute `μ_s, σ_s` on a 60-day holdout, freeze before the training 90-day replay; or use an EWMA prior seeded from public fee + funding distributions.

**Flaw B (§4.1):** 270 ticks bootstrapped to 1500 "within regime" — if the 90d window was a bull regime (kimchi-wide + funding-hot), the policy learns kimchi/funding corners with no exposure to 2022-style drawdown. No survivorship-bias mitigation is documented.
**Fix:** splice in one 30d bearish window (e.g., 2024 Aug flash crash replay via Binance public REST) even if out-of-period.

## 3. Griffin — adverse selection & execution realism — **FAIL**

**Flaw A (§0, Table):** v1 kimchi hold horizon is "minutes–hours," but the allocator decides weights on an 8h cadence. By t+8h a kimchi spike has typically round-tripped; the reward signal is the *integral over a window longer than the alpha half-life*, so good v1 ticks average out with bad ones. This is the doc's own cadence rationale working **against** v1.
**Fix:** decouple cadence per strategy — 8h tick still recomputes weights, but v1's `pnl_v1` is the *peak-to-exit* per-opportunity NetPnL within the window, not the window sum.

**Flaw B (§0 rationale + §6 F-ALLOC-7):** The doc calls 00:00 UTC funding alignment "cleanest attribution." Griffin-lens: that is the *most crowded* moment — every funding farmer on earth enters at the same print. Realized funding capture is systematically below the posted rate due to basis widening. The reward function (`funding_received + basis_change`) captures this mechanically, but the *policy* will learn "ALL_V3 at hot funding" without pricing that the best rates are already arbed.
**Fix:** add `basis_widening_cost` penalty in pretrain using 5-min-post-funding basis delta from historical data; document expected capture ≈ 60-70% of posted rate.

## 4. Kelly/Thorp — sizing & ruin — **WARN**

**Flaw A (§2.1):** 3 of 7 actions are corners (ALL_V1/V2/V3). True Kelly with 3 uncorrelated edges is a continuous simplex allocation; discrete corners force periodic 100% concentration, guaranteeing larger drawdowns than Kelly-optimal. For a hackathon demo this is defensible; for the "we built an allocator" claim it's weak.
**Fix:** either drop corners (keep only mixes + DIVERSIFY = 4 actions, tightens sample budget) or explicitly frame as "action grid is discretized simplex, Kelly-sized within each strategy by producer."

**Flaw B (§5.1):** The all-negative freeze triggers on 24h rolling `raw_reward < −2σ`. In a 2022-style sustained loss regime (all 3 strategies bleeding for weeks), the z-score denominator expands with the loss and `raw_reward` in z-units can stay > −2σ indefinitely — the rail **never fires**. Gap: no capital-at-risk ceiling per tick is documented.
**Fix:** add a dollar-denominated drawdown rail (e.g., cumulative NetPnL since pretrain < −8% book → freeze) independent of z-score, and specify `base_notional` per-tick cap in §7.3.

## 5. Renaissance — data & signal-to-noise — **WARN**

**Flaw A (§1):** `dislocation_regime` OR-merges kimchi premium and USDT-USDC spread. v2's alpha lives in USDT-USDC spread; v3's funding alpha correlates with USDT funding stress which **also** widens USDT-USDC. The state feature and v3's reward are sharing an underlying factor — the allocator learns "wide dislocation → ALL_V3" but the wide-dislocation bit is partly caused by the same shock driving funding. Not leakage (it's a trailing feature), but a redundant-factor trap.
**Fix:** decompose dislocation into `kimchi_bit` and `usdc_spread_bit` (doubles state to 16 cells) — or residualize usdc_spread against funding_median before bucketing.

**Flaw B (§4.1):** Power-law cell occupancy is acknowledged implicitly ("30 visits at BEST") but no low-count handling beyond bootstrap. Bootstrap resamples from the *same* thin cell — it inflates n without adding information. Cells with <5 real ticks should fall back to a hierarchical prior (e.g., shrink toward the marginal-state Q-value), not uniform Q_INIT.
**Fix:** add hierarchical shrinkage: `Q[s,a] = (n·Q_local + k·Q_marginal) / (n+k)` with k=5, documented in §4.5.

---

## Hackathon Judge Defense Kit

**Attack 1: "This is just 3 strategies with a lookup table — where's the RL?"**
> Rebuttal: §2.2 + §7.2 expose UCB1 exploration bonus and second-best Q as payload. Live demo shows regime shift (§10) flipping allocation within 2 ticks — that's learned policy response, not static rules. The Q-for-pricing (executor) and Q-for-allocation (this doc) are distinct tables with different state/action spaces (§8.5).

**Attack 2: "270 pretrain ticks over 63 cells can't learn anything."**
> Rebuttal: §4.3 enumerates all 7 actions per tick (sound under off-policy Q-learning), yielding ~30 effective visits/cell. The F-ALLOC-6 gate (≥3/9 cells converge to a corner) is a hard pre-demo check; failure halts deploy. Caveat: reviewer flagged UCB bonus should denominate in *real* ticks, not enumerated — fix before submission.

**Attack 3: "8h cadence + 90s demo = you're not showing live learning."**
> Rebuttal: §8.1 pre-roll over pretrain data at 5× speed fills `/allocation/history` with ~30 ticks; badge on dashboard explicitly states "demo cadence 30s, prod cadence 8h" (§8.6). Feature windows remain trailing-8h regardless — this is transparent about what's real vs. accelerated.

---

**Overall:** design is shippable for hackathon with 3 must-fix items: (1) Q_INIT raise to match z-scale, (2) hold-out normalization for μ/σ, (3) drawdown rail in dollars. Everything else is polish.
