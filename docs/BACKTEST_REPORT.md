# Capital Allocator — Walk-forward Back-test Report

**Generated**: 2026-04-21 04:29:55 UTC

## 1. Hold-out split (no leakage)
- Total ticks (8h cadence, 5 coins): **271**
- **Cal** (thresholds + reward μ/σ): 178 ticks · 2026-01-21 00:00:00+00:00 → 2026-03-21 00:00:00+00:00
- **Train** (UCB1 Q-learning): 46 ticks · 2026-03-21 08:00:00+00:00 → 2026-04-05 08:00:00+00:00
- **Test** (frozen Q greedy): 47 ticks · 2026-04-05 16:00:00+00:00 → 2026-04-21 00:00:00+00:00

All metrics below are computed on the **test slice only** — the policies never see these ticks during training.

## 2. Policies compared

| # | Policy | Description |
|---|--------|-------------|
| 1 | TrainedQ_walkforward | Q-table learned on the train slice with UCB1, then frozen and run greedy on test |
| 2 | PretrainedQ_full90d  | The shipped Q-table from `consumers/capital_allocator/allocator_q.json` (trained on full timeline) — **leakage check**: should ≥ TrainedQ_walkforward |
| 3 | DIVERSIFY            | Constant 1/3 × (v1, v2, v3). "I don't know" baseline |
| 4 | ALL_V2               | Constant 100% v2 (most stable corner) |
| 5 | ALL_V3_masked        | 100% v3 when funding hot, else DIVERSIFY |
| 6 | Random_uniform       | Uniform random over capability-masked actions |
| 7 | Oracle               | Per-tick ex-post argmax — **upper bound**, not achievable in production |

## 3. Headline metrics

| Policy | Cum R | Mean R | Sharpe | Max DD | Win% | H(act) | Cum $ PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| TrainedQ_walkforward | 8.909 | +0.1896 | 1.855 | 1.550 | 61.7% | 1.224 | +6.21 |
| PretrainedQ_full90d | 13.302 | +0.2830 | 2.912 | 1.137 | 63.8% | 1.042 | +1.93 |
| DIVERSIFY | 4.412 | +0.0939 | 1.492 | 1.948 | 61.7% | -0.000 | +1.60 |
| ALL_V2 | 0.790 | +0.0168 | 0.166 | 4.982 | 61.7% | -0.000 | +9.44 |
| ALL_V3_masked | 10.222 | +0.2175 | 3.236 | 1.109 | 68.1% | 0.544 | +2.07 |
| Random_uniform | 1.736 | +0.0369 | 0.389 | 4.094 | 51.1% | 1.819 | +1.71 |
| Oracle | 33.437 | +0.7114 | 8.799 | 0.317 | 91.5% | 1.576 | +13.90 |

**Reward** is the design §3.2 blend: 0.8·z-score + 0.2·dollar/scale. **Cum $ PnL** is raw dollars (interpretable but smaller — it's the bit before z-blending). **Sharpe** here is the sample-period Sharpe (no annualization, since 46 ticks ≈ 15 days).

## 4. Bootstrap 95% CI (mean reward + Sharpe)

_1000 resamples with replacement over test ticks._

| Policy | mean R 95% CI | Sharpe 95% CI |
|---|---|---|
| TrainedQ_walkforward | [-0.0051, +0.3911] | [-0.048, 3.778] |
| PretrainedQ_full90d | [+0.1096, +0.4821] | [1.257, 4.831] |
| DIVERSIFY | [-0.0219, +0.2236] | [-0.372, 3.517] |
| ALL_V2 | [-0.1717, +0.2163] | [-1.648, 2.261] |
| ALL_V3_masked | [+0.0954, +0.3457] | [1.460, 5.275] |
| Random_uniform | [-0.1457, +0.2173] | [-1.539, 2.300] |
| Oracle | [+0.5524, +0.8851] | [6.806, 11.912] |

## 5. Statistical sanity (paired t-test)

Tests whether the per-tick reward delta differs from zero. p < 0.05 = `*`, < 0.01 = `**`, < 0.001 = `***`.

### vs DIVERSIFY (the "learn nothing" baseline)

| Policy | Δmean | t | p |
|---|---:|---:|---:|
| TrainedQ_walkforward | +0.0957 | +1.204 | 0.2347 n.s. |
| PretrainedQ_full90d | +0.1892 | +2.828 | 0.0069 ** |
| ALL_V2 | -0.0771 | -0.791 | 0.4331 n.s. |
| ALL_V3_masked | +0.1236 | +3.166 | 0.0027 ** |
| Random_uniform | -0.0569 | -0.784 | 0.4369 n.s. |
| Oracle | +0.6176 | +11.183 | 0.0000 *** |

### vs ALL_V2 (the strongest corner baseline)

| Policy | Δmean | t | p |
|---|---:|---:|---:|
| TrainedQ_walkforward | +0.1728 | +1.465 | 0.1496 n.s. |
| PretrainedQ_full90d | +0.2662 | +1.819 | 0.0754 n.s. |
| DIVERSIFY | +0.0771 | +0.791 | 0.4331 n.s. |
| ALL_V3_masked | +0.2007 | +1.983 | 0.0534 n.s. |
| Random_uniform | +0.0201 | +0.164 | 0.8705 n.s. |
| Oracle | +0.6946 | +6.039 | 0.0000 *** |

## 6. Action distribution (how each policy behaved on test)

- **TrainedQ_walkforward**: {'DUAL_FUND': 24, 'ALL_V1': 9, 'KIMCHI_FUND': 8, 'ALL_V2': 6}
- **PretrainedQ_full90d**: {'KIMCHI_FUND': 27, 'ALL_V3': 11, 'ALL_V2': 8, 'ALL_V1': 1}
- **DIVERSIFY**: {'DIVERSIFY': 47}
- **ALL_V2**: {'ALL_V2': 47}
- **ALL_V3_masked**: {'DIVERSIFY': 36, 'ALL_V3': 11}
- **Random_uniform**: {'ALL_V1': 11, 'KIMCHI_DUAL': 10, 'DIVERSIFY': 7, 'ALL_V2': 7, 'KIMCHI_FUND': 6, 'DUAL_FUND': 5, 'ALL_V3': 1}
- **Oracle**: {'ALL_V1': 13, 'ALL_V2': 11, 'DUAL_FUND': 9, 'ALL_V3': 8, 'KIMCHI_FUND': 6}

## 7. Caveats — what these numbers do and DO NOT prove

**What's real**:
- Funding rates + perp_close + spot_close: 90 days of actual Binance fapi data (5 majors).
- v3 PnL formula: `funding_rate × $500 + basis_change × $250` — derived from those real series.
- Regime features `vol` + `funding_median`: real (vol is rolling-8 σ of cross-sectional perp returns).

**What's synthetic / approximated** — affects how to read the table:
- **v1 PnL is AR(1) φ=0.4 σ=$0.80** — Upbit/kimchi data not in this repo. So any policy whose alpha comes from v1 (notably ALL_V1) is reading noise. The v1 column in the action distribution is a red flag.
- **v2 PnL is bootstrap-resampled** from a real 30-day 1s pool of Binance USDT/USDC premium — i.i.d. in time, no autocorrelation. So Sharpe of an ALL_V2 policy is upward-biased vs reality.
- **kimchi_premium + usdc_spread features are synthetic AR(1)** — used as state inputs only, not PnL inputs. They affect which Q cells get visited but don't fake reward.

**Trustworthy comparisons**:
- TrainedQ vs DIVERSIFY → tests whether **state-conditioning helps at all**.
- TrainedQ vs ALL_V3_masked → tests whether **the multi-strategy mix beats the strongest single-corner**.
- TrainedQ vs Oracle → measures **regret** (the unrecoverable gap to ex-post optimal).

**Less trustworthy**:
- TrainedQ vs ALL_V2 → biased by v2's i.i.d. resampling. Treat as a sanity floor, not a real beat.

## 8. What would make this report honest in production
- Wire actual Upbit kimchi parquet → kill the v1 AR(1) and re-run.
- Replace v2 bootstrap with chronologically-aligned 8h dual_quote bins (need 90d 1s data, not 30d).
- Add k-fold walk-forward (k=3) once data is real to detect regime instability.
- Add transaction-cost drag to reward_fn (currently $0 — a real allocator pays Bybit VIP0 0.05%/leg + funding-side-spread + USDC settlement).
