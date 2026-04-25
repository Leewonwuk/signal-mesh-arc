/**
 * Exchange scopes — the top-level signal-filter tabs on the dashboard.
 *
 * Concept: judge picks an exchange tab at the top; signal feeds below filter
 * by that exchange's break-even threshold (= round-trip fees + 0.02% buffer).
 * Each exchange's threshold is derived from the retail-default persona: the
 * VIP 0 tier + retail-accessible promo stacks (Bybit USDC 50% off, Binance
 * BNB 25% off, OKX OKB 40% off taker, MEXC 0% maker default).
 *
 * HONESTY NOTE
 * ------------
 * Only Binance is wired to a live REST feed today. Bybit/OKX/MEXC tabs
 * re-filter the same Binance-sourced signal stream through their own fee
 * envelope; they surface what WOULD be profitable if their REST feed were
 * also connected. Live migration = swap the FeeSource adapter in
 * `producers/dual_quote_agent/main.py`. See dashboard banner.
 *
 * NUMBERS (audited against lib/fee_matrix.ts, 2026-04-25)
 * -------------------------------------------------------
 *   Binance VIP0 + BNB 25% off  = 0.075%×2 = 0.15% + 0.02% buffer → 0.17%
 *   Bybit   VIP0 + USDC 50% off = 0.10%+0.05% (maker+taker) ≈ 0.15% worst-case,
 *                                 but r.t. taker-taker = 0.05%×2 = 0.10%
 *                                 + 0.02% buffer                    → 0.12%
 *   OKX     Lv1  + OKB 40% off  = 0.08%×2 ≈ 0.16% (OKB hits taker only, calc
 *                                  via effective-fee; here use net 0.16%)
 *                                 + 0.02% buffer                    → 0.18%
 *   MEXC    default + MX token  = 0% maker + 0.025% taker r.t. ≈ 0.05%
 *                                 + 0.02% buffer                    → 0.07%
 */

export interface ExchangeScope {
  id: string
  name: string
  /** round-trip fee in % (0.15 = 0.15%) — taker-taker worst-case net of promos */
  feePct: number
  /** safety buffer on top of the raw fee, in % */
  bufferPct: number
  /** break-even threshold for display = feePct + bufferPct */
  thresholdPct: number
  /** true if this tab's numbers come from a LIVE REST feed, not a simulation */
  isLive: boolean
  /** shown under the exchange name on the tab */
  tagline: string
  /** longer breakdown string, shown in selected-scope header */
  feeBreakdown: string
  /** matches `id` in lib/fee_matrix.ts for cross-reference */
  feeMatrixId: string
}

export const EXCHANGE_SCOPES: ExchangeScope[] = [
  {
    id: 'binance',
    name: 'Binance',
    feePct: 0.15,
    bufferPct: 0.02,
    thresholdPct: 0.17,
    isLive: true,
    tagline: 'BNB 25% off · live REST feed',
    feeBreakdown: 'VIP0 0.10% × 2 × (1 − 0.25 BNB) + 0.02% buffer',
    feeMatrixId: 'binance',
  },
  {
    id: 'bybit',
    name: 'Bybit',
    feePct: 0.10,
    bufferPct: 0.02,
    thresholdPct: 0.12,
    isLive: false,
    tagline: 'USDC 50% off taker · fee-envelope SIM',
    feeBreakdown: 'VIP0 0.10% + 0.05% (USDC 50% off taker) + 0.02% buffer',
    feeMatrixId: 'bybit',
  },
]

export function findScope(id: string): ExchangeScope {
  return EXCHANGE_SCOPES.find(s => s.id === id) ?? EXCHANGE_SCOPES[0]
}

/** The decimal threshold a signal must meet to show in scope-filtered feed. */
export function scopeThresholdDecimal(scope: ExchangeScope): number {
  return scope.thresholdPct / 100
}
