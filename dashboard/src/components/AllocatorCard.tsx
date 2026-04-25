/**
 * AllocatorCard — live view of the Capital Allocator RL agent.
 *
 * Polls GET /api/allocation every 2s. Renders:
 *   • the current regime state (state_label or state_idx)
 *   • the 3-way capital split (v1 kimchi, v2 dual-quote, v3 funding) as bars
 *   • the chosen action + Q-defence ("Q=1.23 (2nd best 0.88, explore +0.14)")
 *   • a next-tick countdown
 *   • a red freeze banner when the allocator is safety-railed
 *
 * Design-doc refs: §7.2 payload schema, §8.1 demo cadence badge, §5 freeze rails.
 * Extras (q_value_second_best, exploration_bonus, state_label, next_tick_at,
 * allocation_frozen, frozen_reason) are ALL optional — bridge currently strips
 * them, but a future allocator can supply them without needing a dashboard
 * change. Present them only when defined.
 */
import { useEffect, useMemo, useState } from 'react'

// Nine regime-state labels, aligned with ALLOCATOR_RL_DESIGN §1.
// Encoding: bit0 = dislocation (0 tight, 1 wide), bit1 = funding (0 cold, 1 hot),
// bit2 = vol (0 calm, 1 hot). Index 8 is the `cold` sentinel.
const STATE_LABELS: string[] = [
  'calm / cold-fund / tight',
  'calm / cold-fund / wide',
  'calm / hot-fund / tight',
  'calm / hot-fund / wide',
  'hot-vol / cold-fund / tight',
  'hot-vol / cold-fund / wide',
  'hot-vol / hot-fund / tight',
  'hot-vol / hot-fund / wide',
  'cold (missing features)',
]

const ACTION_LABELS = [
  'ALL_V1',
  'ALL_V2',
  'ALL_V3',
  'KIMCHI_DUAL',
  'DUAL_FUND',
  'KIMCHI_FUND',
  'DIVERSIFY',
]

const ACTION_TOOLTIPS: Record<string, string> = {
  ALL_V1: 'Corner — 100% kimchi premium. KRW FOMO dominates.',
  ALL_V2: 'Corner — 100% dual-quote. Microstructure / chop regime.',
  ALL_V3: 'Corner — 100% funding capture. Bull + hot-funding regime.',
  KIMCHI_DUAL: 'Edge — 50/50 v1+v2. Funding cold, dislocation present.',
  DUAL_FUND: 'Edge — 50/50 v2+v3. Tight dislocation, hot funding.',
  KIMCHI_FUND: 'Edge — 50/50 v1+v3. Wide dislocation, hot funding.',
  DIVERSIFY: 'Centroid — 1/3 each. Cold-state default / "I don\'t know".',
}

interface AllocationWeights {
  v1: number
  v2: number
  v3: number
}

// Schema per /docs/ALLOCATOR_RL_DESIGN.md §7.2, loosened to what the bridge
// actually returns. Extras the bridge may or may not pass through are all
// optional so the card keeps rendering regardless.
interface AllocationEntry {
  tick_id: string
  ts: string
  state_idx: number
  action_idx: number
  action_label: string
  weights: AllocationWeights
  q_values: number[]
  received_at: number
  // Optional — handle if bridge/allocator publishes them
  state_label?: string
  q_value_second_best?: number
  exploration_bonus?: number
  ucb_score?: number
  next_tick_at?: number
  cadence_seconds?: number
  allocation_frozen?: boolean
  frozen_reason?: string | null
}

type AllocationResponse = AllocationEntry | { tick_id: null }

async function fetchAllocation(): Promise<AllocationResponse | null> {
  try {
    const r = await fetch('/api/allocation')
    if (!r.ok) return null
    return (await r.json()) as AllocationResponse
  } catch {
    return null
  }
}

function formatCountdown(ms: number): string {
  if (ms <= 0) return '00:00'
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const ss = s % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const mm = m % 60
    return `${h}h ${String(mm).padStart(2, '0')}m`
  }
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

export function AllocatorCard() {
  const [data, setData] = useState<AllocationResponse | null>(null)
  const [now, setNow] = useState<number>(Date.now())

  // Poll /api/allocation every 2s. The bridge endpoint is in-memory and
  // sub-10ms, so this is essentially free. Matches the cadence of the rest of
  // App.tsx's main tick so both feeds refresh together.
  useEffect(() => {
    let alive = true
    const tick = async () => {
      const d = await fetchAllocation()
      if (!alive) return
      setData(d)
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  // Countdown ticks need a second timer so we don't re-fetch every second.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const isLoaded = data !== null
  const hasEntry = isLoaded && data && 'state_idx' in data && data.tick_id !== null
  const entry = hasEntry ? (data as AllocationEntry) : null

  const stateLabel = entry
    ? entry.state_label ?? STATE_LABELS[entry.state_idx] ?? `state ${entry.state_idx}`
    : ''

  // For the "Q-defence" line, compute 2nd-best from q_values if the allocator
  // didn't pre-compute it. This is the Karpathy-school "why was this chosen"
  // line that pre-empts "is the RL just decoration?" critique.
  const qDefence = useMemo(() => {
    if (!entry) return null
    if (!Array.isArray(entry.q_values) || entry.q_values.length === 0) return null
    const chosen = entry.q_values[entry.action_idx]
    if (chosen == null || !Number.isFinite(chosen)) return null
    const sortedDesc = [...entry.q_values].sort((a, b) => b - a)
    const secondBestRaw =
      entry.q_value_second_best ??
      (sortedDesc[0] === chosen ? sortedDesc[1] : sortedDesc[0])
    const secondBest = Number.isFinite(secondBestRaw) ? secondBestRaw : chosen
    const explore = entry.exploration_bonus
    return { chosen, secondBest, explore }
  }, [entry])

  const countdownMs = entry?.next_tick_at
    ? entry.next_tick_at * 1000 - now
    : null

  return (
    <section className="card allocator-card">
      <div className="alloc-header">
        <h2 style={{ margin: 0 }}>Capital Allocator · Q-learning (Reinforcement Learning)</h2>
        <span className="alloc-cadence-badge" title="decision cadence; feature windows always trailing 8h">
          demo cadence: {entry?.cadence_seconds ? `${entry.cadence_seconds}s` : '20s'} · prod: 8h
        </span>
      </div>

      {!hasEntry && (
        <div className="alloc-empty">
          <div className="alloc-empty-title">Allocator not started</div>
          <div className="alloc-empty-sub">
            run <code>python -m consumers.capital_allocator.main</code> to publish the first tick.
          </div>
          <div className="alloc-skeleton">
            <div className="alloc-skel-state" />
            <div className="alloc-skel-bars">
              <div className="alloc-skel-bar" />
              <div className="alloc-skel-bar" />
              <div className="alloc-skel-bar" />
            </div>
          </div>
        </div>
      )}

      {entry && entry.allocation_frozen && (
        <div className="alloc-freeze-banner">
          <strong>FROZEN</strong>
          <span>{entry.frozen_reason ?? 'safety rail engaged — routing to DIVERSIFY 0.33x'}</span>
        </div>
      )}

      {entry && (
        <div className="alloc-body">
          {/* State + action header */}
          <div className="alloc-top-row">
            <div className="alloc-state-cell">
              <div className="alloc-mini-label">current regime state</div>
              <div className="alloc-state-value">
                s{entry.state_idx}
                <span className="alloc-state-small">/ 9</span>
              </div>
              <div className="alloc-state-sub">{stateLabel}</div>
            </div>

            <div className="alloc-action-cell">
              <div className="alloc-mini-label">chosen action</div>
              <div className="alloc-action-value" title={ACTION_TOOLTIPS[entry.action_label] ?? ''}>
                {entry.action_label}
              </div>
              <div className="alloc-state-sub">
                {ACTION_TOOLTIPS[entry.action_label] ?? `action idx ${entry.action_idx}`}
              </div>
            </div>

            <div className="alloc-q-cell">
              <div className="alloc-mini-label">why this action</div>
              {qDefence ? (
                <div className="alloc-q-defence">
                  <span className="alloc-q-chosen">Q = {qDefence.chosen.toFixed(3)}</span>
                  <span className="alloc-q-sep">·</span>
                  <span className="alloc-q-second">
                    2nd best: {qDefence.secondBest.toFixed(3)}
                  </span>
                  {typeof qDefence.explore === 'number' && (
                    <>
                      <span className="alloc-q-sep">·</span>
                      <span className="alloc-q-explore">
                        explore +{qDefence.explore.toFixed(2)}
                      </span>
                    </>
                  )}
                </div>
              ) : (
                <div className="alloc-q-defence">—</div>
              )}
              <div className="alloc-state-sub">
                argmax over 7 actions; UCB1 exploration bonus added
              </div>
            </div>
          </div>

          {/* Weight bars */}
          <div className="alloc-weights">
            <WeightBar
              label="v1 · kimchi"
              value={entry.weights.v1}
              color="#fb923c"
              titleText="Upbit KRW ↔ Binance USDT"
              provenance="synthetic"
              provenanceTitle="v1 PnL is AR(1) φ=0.4 σ=0.80 — Upbit/Binance kimchi parquet not yet in repo (F1b)"
            />
            <WeightBar
              label="v2 · dual-quote"
              value={entry.weights.v2}
              color="#38bdf8"
              titleText="Binance intra-venue USDT↔USDC"
              provenance="real"
              provenanceTitle="v2 PnL bootstrapped from 91-tick 90d Binance USDT/USDC premium parquet"
            />
            <WeightBar
              label="v3 · funding"
              value={entry.weights.v3}
              color="#4ade80"
              titleText="Spot-long + perp-short funding capture"
              provenance="real"
              provenanceTitle="v3 PnL = funding_rate × $500 + basis × $250, real 90d Binance funding parquet"
            />
          </div>

          {/* Data provenance footer — keeps the synthetic v1 label honest */}
          <div className="alloc-provenance">
            <span className="alloc-provenance-label">data provenance:</span>
            <span className="alloc-provenance-tag is-real" title="real 90d Binance parquet">v2/v3: real 90d</span>
            <span className="alloc-provenance-tag is-synthetic" title="AR(1) — Upbit data backfill pending">v1: synthetic AR(1)</span>
            <span className="alloc-provenance-tag is-real" title="real 90d realized vol + Binance funding REST">regime features: real (kimchi/usdc proxies = AR(1))</span>
          </div>

          {/* Sutton verdict transparency — reward fn switched 2026-04-21 */}
          <div className="alloc-provenance">
            <span className="alloc-provenance-label">reward fn:</span>
            <span className="alloc-provenance-tag is-real" title="z-blend deprecated 2026-04-21 per Sutton-school audit; per-arm σ normalization punished low-σ winning arm v2. See SUBMISSION §12.b for walk-forward backtest p-values.">
              dollar-only (Sutton fix)
            </span>
            <span className="alloc-provenance-tag is-real" title="walk-forward 47-tick hold-out: Q $7.61 vs ALL_V2 $9.44 (p=0.49, statistical tie); Q beats Ridge $6.43 and DIVERSIFY $1.60 (p=0.012)">
              walk-fwd: Q ≈ ALL_V2 (p=0.49)
            </span>
          </div>

          {/* Footer: tick + countdown */}
          <div className="alloc-footer">
            <div className="alloc-footer-cell">
              <span className="alloc-footer-label">tick</span>
              <span className="alloc-footer-val">{entry.tick_id}</span>
            </div>
            <div className="alloc-footer-cell">
              <span className="alloc-footer-label">published</span>
              <span className="alloc-footer-val">
                {new Date(entry.received_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="alloc-footer-cell">
              <span className="alloc-footer-label">next tick in</span>
              <span className="alloc-footer-val">
                {countdownMs !== null ? formatCountdown(countdownMs) : '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function WeightBar({
  label,
  value,
  color,
  titleText,
  provenance,
  provenanceTitle,
}: {
  label: string
  value: number
  color: string
  titleText: string
  provenance?: 'real' | 'synthetic'
  provenanceTitle?: string
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  const muted = pct < 0.5
  const showProvenance = provenance && pct > 0.5
  return (
    <div className="alloc-wbar" title={titleText}>
      <div className="alloc-wbar-label">
        <span>
          {label}
          {showProvenance && (
            <span
              className={`alloc-wbar-prov is-${provenance}`}
              title={provenanceTitle ?? ''}
            >
              {provenance}
            </span>
          )}
        </span>
        <span className={`alloc-wbar-pct ${muted ? 'is-muted' : ''}`}>
          {pct.toFixed(1)}%
        </span>
      </div>
      <div className="alloc-wbar-track">
        <div
          className="alloc-wbar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
