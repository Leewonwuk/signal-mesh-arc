# Capital Allocator Q-table pretrain report

- Generated: 2026-04-21T05:18:34.374564+00:00
- Design: ALLOCATOR_RL_DESIGN v1 (F8-fix)
- Pretrain duration: 4.43s

## Data provenance
- Funding (real): ['ADAUSDT', 'DOGEUSDT', 'SOLUSDT', 'TRXUSDT', 'XRPUSDT']
- v3_pnl: funding_rate*500 + basis_change*500*0.5  (real, from F1b)
- v2_pnl: std(premium_1min) * sqrt(n) * 0.025 * 500, per 8h bin; bootstrapped  (real pool of 91, bootstrap-resampled)
- v1_pnl: AR(1) phi=0.4 sigma=0.80 centered at 0  (**synthetic** — no Upbit/Binance kimchi data in repo per F1b)
- Regime features: funding_median and vol REAL, kimchi_premium and usdc_spread SYNTHETIC

## Holdout split (F8-fix)
- Calibration: 2026-01-21T00:00:00Z → 2026-03-22T00:00:00Z  (180 ticks)
- Training:    2026-03-22T00:00:00Z → 2026-04-21T23:00:00Z  (91 ticks)
- Bootstrap resamples: 1500

## Calibrated reward stats
- μ_v1=+0.0098, σ_v1=0.8024
- μ_v2=+0.2030, σ_v2=0.0247
- μ_v3=-0.0252, σ_v3=0.0549
- DOLLAR_SCALE=0.5000, λ=0.20

## Regime thresholds
- vol_p65 = 0.023803
- funding_p90 = 0.000081
- kimchi_p50 = 0.001600
- usdc_p50 = 0.000795

## Q-table (rows = states, cols = actions, · = unvisited due to mask)

| state | ALL_V1 | ALL_V2 | ALL_V3 | KIMCHI_DUAL | DUAL_FUND | KIMCHI_FUND | DIVERSIFY | argmax |
|---|---|---|---|---|---|---|---|---|
| calm/cold/tight | +0.411 | +0.433 | · | +0.422 | +0.218 | +0.207 | +0.282 | ALL_V2 |
| calm/cold/wide | -0.600 | +0.412 | · | -0.094 | +0.208 | -0.299 | -0.062 | ALL_V2 |
| calm/hot/tight | -0.804 | +0.418 | +0.059 | -0.193 | +0.239 | -0.373 | -0.109 | ALL_V2 |
| calm/hot/wide | -0.715 | +0.407 | +0.037 | -0.154 | +0.222 | -0.339 | -0.090 | ALL_V2 |
| hot/cold/tight | +3.221 | +0.398 | · | +1.810 | +0.258 | +1.669 | +1.246 | ALL_V1 |
| hot/cold/wide | +0.925 | +0.361 | · | +0.643 | +0.223 | +0.505 | +0.457 | ALL_V1 |
| hot/hot/tight | · | · | · | · | · | · | · | UNVISITED |
| hot/hot/wide | -0.562 | +0.393 | +0.011 | -0.085 | +0.202 | -0.276 | -0.053 | ALL_V2 |
| cold-sentinel | · | · | · | · | · | · | · | UNVISITED |

## F-ALLOC-6 gate
- Verdict: **PASS** — 7/9 cells converged to a corner action
- Target: ≥3/9 corner cells (ALL_V1 / ALL_V2 / ALL_V3)

## Visit counts

| state | ALL_V1 | ALL_V2 | ALL_V3 | KIMCHI_DUAL | DUAL_FUND | KIMCHI_FUND | DIVERSIFY |
|---|---|---|---|---|---|---|---|
| calm/cold/tight | 203 | 203 | 0 | 203 | 203 | 203 | 203 |
| calm/cold/wide | 1013 | 1013 | 0 | 1013 | 1013 | 1013 | 1013 |
| calm/hot/tight | 18 | 18 | 18 | 18 | 18 | 18 | 18 |
| calm/hot/wide | 132 | 132 | 132 | 132 | 132 | 132 | 132 |
| hot/cold/tight | 17 | 17 | 0 | 17 | 17 | 17 | 17 |
| hot/cold/wide | 52 | 52 | 0 | 52 | 52 | 52 | 52 |
| hot/hot/tight | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| hot/hot/wide | 65 | 65 | 65 | 65 | 65 | 65 | 65 |
| cold-sentinel | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
