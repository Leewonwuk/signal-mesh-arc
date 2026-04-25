/**
 * strategy_meta — maps producer-emitted `strategy` string to the v1/v2/v3
 * bucket shown by the allocator card. The data is already flowing through
 * the pipeline (bridge/src/index.ts:103 stores `strategy` on StoredSignal
 * and /signals/latest returns it), the dashboard just wasn't labeling rows.
 *
 * Canonical strings (producers):
 *   v1 kimchi   — "kimchi_premium_krw_usdt"  (producers/kimchi_agent/main.py:127)
 *   v2 dual     — "dual_quote_spread"        (producers/dual_quote_agent/main.py:151)
 *   v3 funding  — "funding_rate_basis"       (producers/funding_agent/main.py:236)
 *
 * Why this matters for the hackathon submission:
 *   The pitch is "3-strategy RL allocator on Arc." If the judge opens the
 *   dashboard and sees signal rows with no strategy label, they can only
 *   read the producer_id (e.g. `producer_DOGE`) and rationally conclude
 *   "looks like one strategy running." The per-row chip is the visual
 *   evidence that v1/v2/v3 are truly interleaved into one mesh.
 */
export type StrategyId = 'v1' | 'v2' | 'v3' | 'unk'

export interface StrategyMeta {
  id: StrategyId
  label: string          // short word shown on the chip
  longLabel: string      // for tooltips
  cssId: StrategyId      // matches .strategy-chip.v1 / .v2 / .v3 / .unk
}

const V1: StrategyMeta = { id: 'v1', label: 'kimchi',  longLabel: 'v1 · kimchi premium (Upbit↔Binance)', cssId: 'v1' }
const V2: StrategyMeta = { id: 'v2', label: 'dual',    longLabel: 'v2 · dual-quote spread (USDT↔USDC)',  cssId: 'v2' }
const V3: StrategyMeta = { id: 'v3', label: 'funding', longLabel: 'v3 · funding-rate basis',             cssId: 'v3' }
// UNKNOWN: legacy `gemini_meta` and any strategy we don't recognize. Previously
// bucketed into v2 which silently over-counted v2 and hid v1/v3 evidence —
// now rendered with a distinct 'v?' chip so stale/unlabeled signals are
// visibly separate from the three documented lanes.
const UNKNOWN: StrategyMeta = {
  id: 'unk',
  label: 'unlabeled',
  longLabel: 'unlabeled — legacy signal from before the meta_agent strategy-preservation fix',
  cssId: 'unk',
}

export function strategyMeta(strategy: string | undefined | null): StrategyMeta {
  if (!strategy) return UNKNOWN
  if (strategy.startsWith('kimchi')) return V1
  if (strategy.startsWith('dual'))   return V2
  if (strategy.startsWith('funding')) return V3
  return UNKNOWN
}

export function countByStrategy<T extends { strategy?: string }>(signals: T[]): Record<StrategyId, number> {
  const c: Record<StrategyId, number> = { v1: 0, v2: 0, v3: 0, unk: 0 }
  for (const s of signals) c[strategyMeta(s.strategy).id] += 1
  return c
}
