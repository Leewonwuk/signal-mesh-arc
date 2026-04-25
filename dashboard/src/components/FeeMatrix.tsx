/**
 * FeeMatrix — per-coin × per-venue profitability matrix.
 *
 * Why this exists: FeeExplorer lets you pick ONE persona and see ONE number.
 * Judges asking "do fees really differ per coin?" need a matrix answer.
 *
 * Strategy:
 *   • Rows = demo symbols (DOGE / XRP / SOL — these are the ones the live
 *     demo.run_demo harness animates).
 *   • Cols = the 5 venues from EXCHANGE_FEE_MATRIX, each evaluated at their
 *     retail-default VIP tier + retail-accessible promos stacked. This is
 *     what a real retail operator would actually see today.
 *   • Cell value = round-trip taker-taker fee for alt/USDC pair on that venue.
 *   • Cell colour = green if realized mean premium for that symbol in the
 *     live demo stream exceeds that fee (profitable), red otherwise,
 *     grey if the venue is structurally arb-incompatible (Coinbase).
 *   • Footer = realized mean premium per coin, so the judge sees the input
 *     the colouring was computed against.
 *
 * No bridge mutation — this is a read-only analytics layer over signals
 * already in App state. Dynamic because the realized-mean updates as
 * signals flow.
 */
import { useMemo } from 'react'
import {
  EXCHANGE_FEE_MATRIX,
  EXCHANGE_ORDER,
  type Exchange,
} from '../lib/fee_matrix'
import { calculateEffectiveFee } from '../lib/fee_calculator'

interface Signal {
  symbol: string
  premium_rate: number
}

interface Props {
  signals: Signal[]
  demoSymbols?: string[]
  /** When set, highlights the active scope venue's column and shows the threshold line.
   *  NOTE (2026-04-26 cleanup): the matrix and the FeeExplorer have independent
   *  selectors. Showing the v2 scope here while the FeePersonaExplorer sits on a
   *  different venue confused judges in pre-recording captures. App.tsx now omits
   *  these props, so the matrix renders the per-venue retail-default fees only —
   *  no implicit "active scope" claim. The props are kept for future ifecake we
   *  decide to lift state, but are no-ops when undefined. */
  scopeThresholdPct?: number
  scopeLabel?: string
}

const DEFAULT_DEMO_SYMBOLS = ['DOGE', 'XRP', 'SOL']
/** Below this n, the realized-mean cell is rendered as a neutral dash (—)
 *  instead of pass/fail. Statistically thin samples (n<30) shouldn't drive
 *  ✓/✗ judgments — flagged in pre-recording review (DOGE n=10 was producing
 *  cherry-picked-looking decisions across 5 venue columns). */
const MIN_N_FOR_PASS_FAIL = 30

/** Retail-scenario default fee for a venue using alt/USDC pair. */
function retailDefaultFee(ex: Exchange, symbol: string) {
  const tier = ex.vipTiers.find(t => t.retailDefault) ?? ex.vipTiers[0]
  const discountIds = ex.discounts.filter(d => d.retailAccessible).map(d => d.id)
  const pair = `${symbol}/USDC`
  const fee = calculateEffectiveFee({
    exchangeId: ex.id,
    vipTierId: tier.id,
    discountIds,
    pair,
  })
  return {
    roundTrip: fee.roundTripTakerTaker,
    tierName: tier.name,
    promoLabel:
      ex.discounts.filter(d => d.retailAccessible).map(d => d.label).join(' + ') || null,
  }
}

/** Arithmetic mean of a non-empty array. Returns null on empty. */
function mean(arr: number[]): number | null {
  if (arr.length === 0) return null
  let s = 0
  for (const v of arr) s += v
  return s / arr.length
}

export function FeeMatrix({
  signals,
  demoSymbols = DEFAULT_DEMO_SYMBOLS,
  scopeThresholdPct,
  scopeLabel,
}: Props) {
  // Group recent signals by symbol; cap at 200 each so early cold-start noise
  // doesn't dominate the average once production volume builds.
  const realized = useMemo(() => {
    const byCoin: Record<string, number[]> = {}
    for (const c of demoSymbols) byCoin[c] = []
    for (const s of signals) {
      if (byCoin[s.symbol] && byCoin[s.symbol].length < 200) {
        byCoin[s.symbol].push(s.premium_rate)
      }
    }
    const out: Record<string, { mean: number | null; n: number }> = {}
    for (const c of demoSymbols) {
      out[c] = { mean: mean(byCoin[c]), n: byCoin[c].length }
    }
    return out
  }, [signals, demoSymbols])

  // Pre-compute per-venue retail fee (same structure for every symbol; we
  // recompute per (venue, symbol) anyway for Binance/Coinbase pair overrides).
  const feeGrid = useMemo(() => {
    const out: Record<string, Record<string, ReturnType<typeof retailDefaultFee>>> = {}
    for (const vid of EXCHANGE_ORDER) {
      const ex = EXCHANGE_FEE_MATRIX[vid]
      out[vid] = {}
      for (const sym of demoSymbols) {
        out[vid][sym] = retailDefaultFee(ex, sym)
      }
    }
    return out
  }, [demoSymbols])

  return (
    <section className="fee-matrix card">
      <div className="fee-matrix-header">
        <h2>Per-coin × per-venue profitability</h2>
        <span className="meta">
          Retail default persona on each venue (VIP 0/Lv 1 + retail-accessible promos stacked).
          Cell = round-trip taker-taker fee; colour = realized mean premium vs cell fee.
        </span>
      </div>

      <div className="fee-matrix-scroll">
        <table className="fee-matrix-table">
          <thead>
            <tr>
              <th className="fee-matrix-corner">Coin ↓ / Venue →</th>
              {EXCHANGE_ORDER.map(vid => {
                const ex = EXCHANGE_FEE_MATRIX[vid]
                return (
                  <th key={vid} className="fee-matrix-col-header">
                    <div className="fee-matrix-col-name">{ex.name}</div>
                    <div className="fee-matrix-col-sub">
                      {feeGrid[vid][demoSymbols[0]].tierName}
                      {feeGrid[vid][demoSymbols[0]].promoLabel && ' + promo'}
                    </div>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {demoSymbols.map(sym => (
              <tr key={sym}>
                <th className="fee-matrix-row-header">
                  <span className="fee-matrix-sym">{sym}</span>
                  <span className="fee-matrix-realized">
                    {realized[sym].mean != null
                      ? `avg ${(realized[sym].mean! * 100).toFixed(3)}%`
                      : 'awaiting data'}
                    {realized[sym].n > 0 && (
                      <span className="fee-matrix-n"> · n={realized[sym].n}</span>
                    )}
                  </span>
                </th>
                {EXCHANGE_ORDER.map(vid => {
                  const ex = EXCHANGE_FEE_MATRIX[vid]
                  const cell = feeGrid[vid][sym]
                  const rtPct = cell.roundTrip * 100
                  const notSupported = !ex.supportsDualQuoteArb
                  const meanRate = realized[sym].mean
                  const n = realized[sym].n
                  let cls = 'fee-matrix-cell'
                  let marker = ''
                  if (notSupported) {
                    cls += ' is-na'
                    marker = 'N/A'
                  } else if (meanRate == null) {
                    cls += ' is-idle'
                  } else if (n < MIN_N_FOR_PASS_FAIL) {
                    // Statistically thin — show the fee but no pass/fail judgment yet.
                    cls += ' is-warmup'
                    marker = '—'
                  } else if (meanRate > cell.roundTrip) {
                    cls += ' is-profitable'
                    marker = '✓'
                  } else {
                    cls += ' is-unprofitable'
                    marker = '✗'
                  }
                  return (
                    <td key={vid} className={cls}>
                      {notSupported ? (
                        <>
                          <span className="fee-matrix-cell-val is-muted">N/A</span>
                          <span className="fee-matrix-cell-sub">alt/USDT missing</span>
                        </>
                      ) : (
                        <>
                          <span className="fee-matrix-cell-val">
                            {rtPct.toFixed(3)}%
                          </span>
                          {marker && (
                            <span className="fee-matrix-cell-marker">{marker}</span>
                          )}
                        </>
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="fee-matrix-legend">
        <span className="fee-matrix-legend-chip is-profitable">✓ realized avg &gt; fee (n≥{MIN_N_FOR_PASS_FAIL})</span>
        <span className="fee-matrix-legend-chip is-unprofitable">✗ realized avg &lt; fee (n≥{MIN_N_FOR_PASS_FAIL})</span>
        <span className="fee-matrix-legend-chip is-warmup">— warming up (n&lt;{MIN_N_FOR_PASS_FAIL})</span>
        <span className="fee-matrix-legend-chip is-na">N/A structurally unavailable</span>
        <span className="fee-matrix-legend-meta">
          fees evaluated on alt/USDC pair · round-trip taker-taker worst case
        </span>
        {scopeThresholdPct != null && (
          <span className="fee-matrix-legend-meta">
            · v2 scope: <strong>{scopeLabel ?? 'venue'} {scopeThresholdPct.toFixed(2)}%</strong> (separate from FeeExplorer)
          </span>
        )}
      </div>
    </section>
  )
}
