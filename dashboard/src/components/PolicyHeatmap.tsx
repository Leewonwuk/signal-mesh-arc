/**
 * PolicyHeatmap — 9-state × 7-action Q-table visit visualisation.
 *
 * Polls GET /api/allocation/history?limit=200 every 5s, buckets each entry
 * into its (state_idx, action_idx) cell, and renders a 9×7 grid where darker
 * green = more frequently picked in that regime. This is the visualisation
 * behind the F-ALLOC-6 success gate: "≥3/9 state cells must converge to a
 * corner action (ALL_V1, ALL_V2, or ALL_V3)."
 *
 * Why 5s poll (vs 2s on AllocatorCard): heatmap aggregates over history; the
 * marginal value of refreshing faster is near-zero, and the 200-entry
 * response is ~30KB, so we don't want to pull it every 2s unnecessarily.
 */
import { useEffect, useMemo, useState } from 'react'

const NUM_STATES = 9
const NUM_ACTIONS = 7

// Short state labels — column headers for a compact grid. Full labels live
// in AllocatorCard. Keep in sync with ALLOCATOR_RL_DESIGN §1 encoding.
const STATE_ROW_LABELS: string[] = [
  'calm / cold / tight',
  'calm / cold / wide',
  'calm / hot / tight',
  'calm / hot / wide',
  'hot / cold / tight',
  'hot / cold / wide',
  'hot / hot / tight',
  'hot / hot / wide',
  'cold (missing)',
]

const ACTION_COL_LABELS: string[] = [
  'ALL_V1',
  'ALL_V2',
  'ALL_V3',
  'KIMCHI_DUAL',
  'DUAL_FUND',
  'KIMCHI_FUND',
  'DIVERSIFY',
]

// Corner actions are indices 0, 1, 2 (per design §2.1). F-ALLOC-6 success
// criterion: ≥3/9 state rows have their argmax land on a corner.
const CORNER_ACTIONS = new Set([0, 1, 2])

interface AllocationEntry {
  tick_id: string
  state_idx: number
  action_idx: number
  action_label: string
  received_at: number
}

interface HistoryResponse {
  entries: AllocationEntry[]
  count: number
}

async function fetchHistory(): Promise<HistoryResponse | null> {
  try {
    const r = await fetch('/api/allocation/history?limit=200')
    if (!r.ok) return null
    return (await r.json()) as HistoryResponse
  } catch {
    return null
  }
}

export function PolicyHeatmap() {
  const [entries, setEntries] = useState<AllocationEntry[] | null>(null)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const h = await fetchHistory()
      if (!alive) return
      setEntries(h?.entries ?? [])
    }
    tick()
    const id = setInterval(tick, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  // Count per (state, action). Guard against out-of-range idxs just in case
  // the bridge ever loosens validation.
  const { counts, maxCount, cornerHits, populatedStates } = useMemo(() => {
    const counts: number[][] = Array.from({ length: NUM_STATES }, () =>
      Array(NUM_ACTIONS).fill(0),
    )
    if (!entries) {
      return { counts, maxCount: 0, cornerHits: 0, populatedStates: 0 }
    }
    for (const e of entries) {
      if (
        e.state_idx >= 0 &&
        e.state_idx < NUM_STATES &&
        e.action_idx >= 0 &&
        e.action_idx < NUM_ACTIONS
      ) {
        counts[e.state_idx][e.action_idx] += 1
      }
    }

    // Per-row argmax — is this regime converging to a corner action?
    let cornerHits = 0
    let populatedStates = 0
    for (let s = 0; s < NUM_STATES; s++) {
      const row = counts[s]
      const rowSum = row.reduce((a, b) => a + b, 0)
      if (rowSum === 0) continue
      populatedStates += 1
      let bestIdx = 0
      let bestVal = -1
      for (let a = 0; a < NUM_ACTIONS; a++) {
        if (row[a] > bestVal) {
          bestVal = row[a]
          bestIdx = a
        }
      }
      if (CORNER_ACTIONS.has(bestIdx)) cornerHits += 1
    }

    let maxCount = 0
    for (let s = 0; s < NUM_STATES; s++) {
      for (let a = 0; a < NUM_ACTIONS; a++) {
        if (counts[s][a] > maxCount) maxCount = counts[s][a]
      }
    }
    return { counts, maxCount, cornerHits, populatedStates }
  }, [entries])

  const totalTicks = entries?.length ?? 0
  const hasData = totalTicks > 0
  const passGate = cornerHits >= 3

  return (
    <section className="card policy-heatmap">
      <div className="alloc-header">
        <h2 style={{ margin: 0 }}>Policy heatmap · Q-table visits</h2>
        <span className="alloc-cadence-badge" title="polls /api/allocation/history every 5s">
          {totalTicks} ticks · 9 states × 7 actions
        </span>
      </div>

      {!hasData && (
        <div className="alloc-empty">
          <div className="alloc-empty-title">No allocator history yet</div>
          <div className="alloc-empty-sub">
            run <code>python -m consumers.capital_allocator.main</code> — each published tick
            will light one cell below.
          </div>
          <div className="heatmap-grid heatmap-grid-skeleton" aria-hidden>
            {Array.from({ length: NUM_STATES * NUM_ACTIONS }).map((_, i) => (
              <div className="heatmap-cell is-skeleton" key={i} />
            ))}
          </div>
        </div>
      )}

      {hasData && (
        <>
          <div className="heatmap-wrapper">
            {/* Column header row */}
            <div className="heatmap-col-headers">
              <div className="heatmap-corner-cell" />
              {ACTION_COL_LABELS.map((label, ai) => (
                <div
                  className={`heatmap-col-label ${CORNER_ACTIONS.has(ai) ? 'is-corner' : ''}`}
                  key={label}
                >
                  {label}
                </div>
              ))}
            </div>

            {/* Each row = one state */}
            {STATE_ROW_LABELS.map((rowLabel, si) => {
              const row = counts[si]
              const rowSum = row.reduce((a, b) => a + b, 0)
              let argmax = -1
              let bestVal = -1
              for (let a = 0; a < NUM_ACTIONS; a++) {
                if (row[a] > bestVal) {
                  bestVal = row[a]
                  argmax = a
                }
              }
              const isConverged = rowSum > 0 && CORNER_ACTIONS.has(argmax)

              return (
                <div className="heatmap-row" key={rowLabel}>
                  <div
                    className={`heatmap-row-label ${rowSum === 0 ? 'is-empty' : ''} ${isConverged ? 'is-converged' : ''}`}
                    title={`state ${si}: ${rowSum} total picks`}
                  >
                    <span className="heatmap-row-si">s{si}</span>
                    <span className="heatmap-row-text">{rowLabel}</span>
                  </div>
                  {row.map((count, ai) => {
                    const intensity = maxCount > 0 ? count / maxCount : 0
                    const isArgmax = count > 0 && ai === argmax
                    return (
                      <div
                        className={`heatmap-cell ${isArgmax ? 'is-argmax' : ''} ${count === 0 ? 'is-zero' : ''}`}
                        key={ai}
                        style={{
                          background: cellColor(intensity),
                        }}
                        title={`${rowLabel} × ${ACTION_COL_LABELS[ai]}: ${count} picks`}
                      >
                        {count > 0 ? count : ''}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>

          <div className="heatmap-footer">
            <div className="heatmap-legend">
              <span className="heatmap-legend-label">darker = more frequently chosen in this regime</span>
              <div className="heatmap-legend-bar">
                <span className="heatmap-legend-tick">0</span>
                <div className="heatmap-legend-gradient" />
                <span className="heatmap-legend-tick">{maxCount}</span>
              </div>
            </div>
            <div className={`heatmap-gate ${passGate ? 'is-pass' : 'is-fail'}`}>
              <span className="heatmap-gate-icon">{passGate ? '✓' : '⚠'}</span>
              <span>
                F-ALLOC-6: {cornerHits}/{populatedStates > 0 ? populatedStates : 9} populated states
                converged to a corner {passGate ? '(pass)' : '(need ≥3)'}
              </span>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

// Gradient from neutral (low-alpha card background) to saturated green.
// intensity ∈ [0, 1]; 0 produces a near-invisible wash, 1 produces solid accent.
function cellColor(intensity: number): string {
  if (intensity <= 0) return 'rgba(74, 222, 128, 0.04)'
  // Mix between var(--bg-card-hi)-ish (low intensity) and var(--green) (high).
  const alpha = 0.1 + 0.75 * intensity
  return `rgba(74, 222, 128, ${alpha.toFixed(3)})`
}
