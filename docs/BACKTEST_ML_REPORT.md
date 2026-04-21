# Capital Allocator — RL vs ML Bake-off

**Generated**: 2026-04-21 04:39:50 UTC

## 1. Why this report exists

Original design used tabular Q-learning. A DS critique caught the framing error:

> The setup is **not an MDP**. Our action does not affect next tick's vol/funding/kimchi/usdc
> (the market is much bigger than us), and the cadence is 8h. Reframed honestly, this is a
> **contextual bandit** — which collapses to supervised regression: predict per-strategy
> expected pnl from current features, then argmax expected reward over 7 actions.

This report runs Ridge regression and LightGBM on the **identical** walk-forward split and
compares them to the Q-table on the **identical** test slice with the **identical** reward
function. Whichever policy generalizes better wins.

## 2. Hold-out split

- **Cal** (μ/σ + thresholds): 178 ticks · 2026-01-21 00:00:00+00:00 → 2026-03-21 00:00:00+00:00
- **Train** (model fit / Q-learning): 46 ticks · 2026-03-21 08:00:00+00:00 → 2026-04-05 08:00:00+00:00
- **Test** (frozen, never seen): 47 ticks · 2026-04-05 16:00:00+00:00 → 2026-04-21 00:00:00+00:00

## 3. Headline metrics

| Policy | Cum R | Mean R | Sharpe | Max DD | Win% | Cum $ PnL |
|---|---:|---:|---:|---:|---:|---:|
| **Ridge** | 14.100 | +0.3000 | 3.251 | 1.524 | 76.6% | +6.43 |
| **LightGBM** | 5.416 | +0.1152 | 0.966 | 3.458 | 63.8% | +5.65 |
| **TrainedQ_walkforward** | 8.909 | +0.1896 | 1.855 | 1.550 | 61.7% | +6.21 |
| **PretrainedQ_full90d** | 13.302 | +0.2830 | 2.912 | 1.137 | 63.8% | +1.93 |
| **DIVERSIFY** | 4.412 | +0.0939 | 1.492 | 1.948 | 61.7% | +1.60 |
| **ALL_V2** | 0.790 | +0.0168 | 0.166 | 4.982 | 61.7% | +9.44 |
| **ALL_V3_masked** | 10.222 | +0.2175 | 3.236 | 1.109 | 68.1% | +2.07 |
| **Random_uniform** | 1.736 | +0.0369 | 0.389 | 4.094 | 51.1% | +1.71 |
| **Oracle** | 33.437 | +0.7114 | 8.799 | 0.317 | 91.5% | +13.90 |

## 4. Bootstrap 95% CI (mean reward)

| Policy | mean R 95% CI | Sharpe 95% CI |
|---|---|---|
| Ridge | [+0.1158, +0.4701] | [1.174, 5.972] |
| LightGBM | [-0.1062, +0.3498] | [-0.848, 3.335] |
| TrainedQ_walkforward | [-0.0020, +0.3847] | [-0.021, 3.750] |
| PretrainedQ_full90d | [+0.1076, +0.4820] | [1.233, 4.772] |
| DIVERSIFY | [-0.0229, +0.2152] | [-0.365, 3.550] |
| ALL_V2 | [-0.1812, +0.2056] | [-1.745, 2.276] |
| ALL_V3_masked | [+0.0861, +0.3504] | [1.415, 5.383] |
| Random_uniform | [-0.1371, +0.2257] | [-1.476, 2.393] |
| Oracle | [+0.5729, +0.8722] | [6.938, 12.246] |

## 5. Statistical sanity (paired t-test on per-tick reward delta)

`***` p<0.001, `**` p<0.01, `*` p<0.05, `n.s.` otherwise.

### vs DIVERSIFY (the "learn nothing" baseline)

| Policy | Δmean | t | p |
|---|---:|---:|---|
| Ridge | +0.2061 | +2.497 | 0.0162 * |
| LightGBM | +0.0214 | +0.214 | 0.8314 n.s. |
| TrainedQ_walkforward | +0.0957 | +1.204 | 0.2347 n.s. |
| PretrainedQ_full90d | +0.1892 | +2.828 | 0.0069 ** |
| ALL_V2 | -0.0771 | -0.791 | 0.4331 n.s. |
| ALL_V3_masked | +0.1236 | +3.166 | 0.0027 ** |
| Random_uniform | -0.0569 | -0.784 | 0.4369 n.s. |
| Oracle | +0.6176 | +11.183 | 0.0000 *** |

### vs ALL_V3_masked (the strongest rule-based competitor)

| Policy | Δmean | t | p |
|---|---:|---:|---:|
| Ridge | +0.0825 | +1.054 | 0.2972 n.s. |
| LightGBM | -0.1023 | -0.946 | 0.3493 n.s. |
| TrainedQ_walkforward | -0.0279 | -0.289 | 0.7740 n.s. |
| PretrainedQ_full90d | +0.0655 | +1.141 | 0.2599 n.s. |
| DIVERSIFY | -0.1236 | -3.166 | 0.0027 ** |
| ALL_V2 | -0.2007 | -1.983 | 0.0534 n.s. |
| Random_uniform | -0.1805 | -2.051 | 0.0460 * |
| Oracle | +0.4939 | +7.728 | 0.0000 *** |

## 6. ML model fit diagnostics

In-sample vs out-of-sample R² for each per-strategy regressor.
Negative test R² means the model predicts worse than the test mean — overfit signal.

### Ridge

| target | train R² | test R² |
|---|---:|---:|
| pnl_v1 | +0.073 | -0.268 |
| pnl_v2 | +0.023 | -0.055 |
| pnl_v3 | +0.256 | +0.093 |

**Feature importance / coefficient:**

| target | vol | funding_median | kimchi_premium | usdc_spread |
|---|---:|---:|---:|---:|
| pnl_v1 | -0.154 | +0.002 | +0.030 | -0.053 |
| pnl_v2 | -0.002 | +0.001 | +0.000 | -0.002 |
| pnl_v3 | +0.005 | +0.015 | +0.005 | +0.003 |

### LightGBM

| target | train R² | test R² |
|---|---:|---:|
| pnl_v1 | +0.574 | -0.058 |
| pnl_v2 | -0.000 | -0.110 |
| pnl_v3 | +0.498 | +0.031 |

**Feature importance / coefficient:**

| target | vol | funding_median | kimchi_premium | usdc_spread |
|---|---:|---:|---:|---:|
| pnl_v1 | +52.000 | +79.000 | +35.000 | +60.000 |
| pnl_v2 | +0.000 | +0.000 | +0.000 | +0.000 |
| pnl_v3 | +95.000 | +67.000 | +35.000 | +0.000 |

## 7. Action distribution (test slice)

- **Ridge**: {'ALL_V2': 23, 'DUAL_FUND': 14, 'ALL_V3': 10}
- **LightGBM**: {'ALL_V2': 20, 'DUAL_FUND': 16, 'ALL_V1': 9, 'ALL_V3': 2}
- **TrainedQ_walkforward**: {'DUAL_FUND': 24, 'ALL_V1': 9, 'KIMCHI_FUND': 8, 'ALL_V2': 6}
- **PretrainedQ_full90d**: {'KIMCHI_FUND': 27, 'ALL_V3': 11, 'ALL_V2': 8, 'ALL_V1': 1}
- **DIVERSIFY**: {'DIVERSIFY': 47}
- **ALL_V2**: {'ALL_V2': 47}
- **ALL_V3_masked**: {'DIVERSIFY': 36, 'ALL_V3': 11}
- **Random_uniform**: {'ALL_V1': 11, 'KIMCHI_DUAL': 10, 'DIVERSIFY': 7, 'ALL_V2': 7, 'KIMCHI_FUND': 6, 'DUAL_FUND': 5, 'ALL_V3': 1}
- **Oracle**: {'ALL_V1': 13, 'ALL_V2': 11, 'DUAL_FUND': 9, 'ALL_V3': 8, 'KIMCHI_FUND': 6}

## 8. Read-out — which model should ship?

Decision rule, in priority order:

1. **Significantly beats DIVERSIFY (p < 0.05)**? If only one of {Ridge, LightGBM, TrainedQ}
   passes this gate, that's the recommendation.
2. **Significantly beats ALL_V3_masked**? If a learned model can't beat a 1-line rule,
   ship the rule.
3. **Test R² > 0** for at least one strategy? If both Ridge and LightGBM produce negative
   test R² across all three pnl targets, the features are noise on this slice.
4. **Pick the lowest-variance winner** — ties go to Ridge over LightGBM (smaller, more
   interpretable, easier to ship).

## 9. Caveats — what these numbers do NOT cover

- Same v1=synthetic AR(1) and v2=bootstrap-resampled limitations as `BACKTEST_REPORT.md` §7.
- Train slice is **46 ticks** — borderline for LightGBM. Negative test R² is expected on small data.
- No transaction-cost drag in `reward_fn` — production must subtract fees per leg.
- No regime-shift stress test (e.g. Mar→Apr funding regime change). 47 test ticks ≈ 15 days.
- Ridge / LGBM use the SAME 4 binned features the Q-table sees — fair competitor, but 
  not the only feature set possible. A richer feature build (lag-k funding, vol-of-vol, 
  cross-strategy correlation) might widen the gap.
