# Backtest — v1/v2-aware Rule Comparison

**Hypothesis:** v3 fires only ~10% of ticks. v1 PnL is synthetic AR(1) noise.
v2 (real USDC dual-quote) is the daily workhorse but z-score reward penalizes its low σ.
Goal: prove that an explicit v1/v2 gate beats the 9-state Q-table.

- Test slice: 47 ticks (8h cadence)
- Funding hot: 11 ticks (23.4%)
- Kimchi wide: 30 ticks (63.8%)
- USDC wide: 21 ticks (44.7%)

## Leaderboard (sorted by dollar PnL)

| policy | cum_R | $pnl | sharpe | win% | p (vs DIV $) | p (vs V2 $) |
|---|---:|---:|---:|---:|---:|---:|
| ALL_V2 | 18.88 | 9.44 | 65.12 | 100.0% | 0.0001 | nan |
| TrainedQ_walkforward | 15.21 | 7.61 | 2.89 | 83.0% | 0.0119 | 0.4936 |
| RULE_A_V2_DEFAULT | 14.78 | 7.39 | 12.55 | 91.5% | 0.0032 | 0.0005 |
| RULE_B2_FULL_GATED_V1SAFE | 14.78 | 7.39 | 12.55 | 91.5% | 0.0032 | 0.0005 |
| RULE_B_FULL_GATED | 8.77 | 4.38 | 1.41 | 76.6% | 0.2442 | 0.1160 |
| ALL_V3_masked | 4.14 | 2.07 | 1.26 | 66.0% | 0.5230 | 0.0001 |
| PretrainedQ_full90d | 3.86 | 1.93 | 0.66 | 63.8% | 0.8550 | 0.0142 |
| DIVERSIFY | 3.20 | 1.60 | 0.88 | 59.6% | nan | 0.0001 |

## Interpretation

- **Dollar PnL** is the unbiased ground-truth metric (no z-score artifact).
- ALL_V2 / RULE_A / RULE_B winning on $pnl confirms the workhorse hypothesis.
- If RULE_A beats ALL_V2 with p < 0.05 (dollar test), the funding gate adds real value.
- RULE_B will look bad if v1 fires often, since v1 PnL is synthetic noise (AR(1)).
  RULE_B2 is the production-honest version: v1 fallback to v2 until Upbit data lands.

## Production recommendation

Pick the row with: best dollar PnL, p < 0.05 vs DIVERSIFY, and explainable in 2 lines.
