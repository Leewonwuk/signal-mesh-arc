/**
 * FeeExplorer — multi-exchange tabbed configurator.
 *
 * Top-level story:
 *   • The judge picks an exchange tab (Bybit, Binance, OKX, Coinbase, MEXC).
 *   • For that exchange, they pick a VIP tier and toggle any discounts /
 *     promotions that apply to them. They can also pick which pair is being
 *     traded (matters for Binance USDC promo, Coinbase stablepair).
 *   • The big "effective fee" badge updates live. Below it, break-even %,
 *     expected daily NetPnL, and expected trades/coin/day recompute.
 *   • If the exchange is structurally arb-incompatible (Coinbase), a banner
 *     explains why, and the LiveMetrics card disables its frequency estimate.
 *
 * This is not talking to the Python side — it's a pricing-transparency layer
 * so the user can validate the same assumption the Q-learning fee model was
 * compiled against (FEE_ROUND_TRIP constant in pricing_policy.py).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  EXCHANGE_FEE_MATRIX,
  EXCHANGE_ORDER,
  V13_PAIRS,
  type Exchange,
} from '../lib/fee_matrix'
import {
  calculateEffectiveFee,
  estimateDailyNetPnl,
  estimateFrequency,
  V13_THRESHOLD_DEFAULT,
} from '../lib/fee_calculator'

type SyncStatus =
  | { kind: 'idle' }
  | { kind: 'syncing' }
  | { kind: 'applied'; at: number; label: string }
  | { kind: 'error'; message: string }

const V13_COINS = 9
const V13_NOTIONAL_USD = 494

function initialPersonaForExchange(ex: Exchange) {
  const defaultTier = ex.vipTiers.find(t => t.retailDefault) ?? ex.vipTiers[0]
  const defaultDiscounts = ex.discounts.filter(d => d.retailAccessible).map(d => d.id)
  // Pick a default pair that's plausibly arb-able
  const pair =
    (V13_PAIRS as readonly string[]).find(p => p.endsWith('/USDC')) ?? V13_PAIRS[0]
  return { vipTierId: defaultTier.id, discountIds: defaultDiscounts, pair }
}

interface PersonaState {
  [exchangeId: string]: {
    vipTierId: string
    discountIds: string[]
    pair: string
  }
}

export function FeeExplorer() {
  const [activeId, setActiveId] = useState<string>(EXCHANGE_ORDER[0])
  const [personas, setPersonas] = useState<PersonaState>(() => {
    const out: PersonaState = {}
    for (const id of EXCHANGE_ORDER) {
      out[id] = initialPersonaForExchange(EXCHANGE_FEE_MATRIX[id])
    }
    return out
  })
  const [threshold, setThreshold] = useState<number>(V13_THRESHOLD_DEFAULT)

  const activeExchange = EXCHANGE_FEE_MATRIX[activeId]
  const activePersona = personas[activeId]

  const setPersona = (
    exchangeId: string,
    patch: Partial<PersonaState[string]>,
  ) => {
    setPersonas(prev => ({
      ...prev,
      [exchangeId]: { ...prev[exchangeId], ...patch },
    }))
  }

  const fee = useMemo(
    () =>
      calculateEffectiveFee({
        exchangeId: activeId,
        vipTierId: activePersona.vipTierId,
        discountIds: activePersona.discountIds,
        pair: activePersona.pair,
      }),
    [activeId, activePersona],
  )

  const freq = useMemo(() => estimateFrequency(fee, threshold), [fee, threshold])
  const pnl = useMemo(
    () => estimateDailyNetPnl(fee, threshold, V13_NOTIONAL_USD, V13_COINS),
    [fee, threshold],
  )

  const thresholdBp = threshold * 10000
  const feeBp = fee.roundTripTakerTaker * 10000
  const edgeBp = Math.max(0, thresholdBp - feeBp)
  const profitable = edgeBp > 0

  // ── Live bridge sync ────────────────────────────────────────────────
  // Whenever the user mutates the persona, push the effective fee + threshold
  // to POST /api/policy/persona (proxied to the Node bridge). The bridge uses
  // that to gate /signals/publish tier promotions and recompute
  // /economics/summary, so the judge's knob-turn is visible in the live
  // counters (premium lane rises/collapses within one producer tick).
  const [sync, setSync] = useState<SyncStatus>({ kind: 'idle' })
  const didInitialSync = useRef(false)
  const debounceRef = useRef<number | null>(null)

  useEffect(() => {
    // Debounce so radio-mashing doesn't flood the bridge. 300ms is long enough
    // to coalesce a burst, short enough to feel live.
    if (debounceRef.current != null) {
      window.clearTimeout(debounceRef.current)
    }
    const payload = {
      exchangeId: activeExchange.id,
      label: `${activeExchange.name} · ${
        activeExchange.vipTiers.find(t => t.id === activePersona.vipTierId)?.name ?? activePersona.vipTierId
      }`,
      feeRoundTrip: Number(fee.roundTripTakerTaker.toFixed(6)),
      thresholdRate: Number(threshold.toFixed(6)),
      supportsDualQuoteArb: activeExchange.supportsDualQuoteArb,
    }
    const fire = async () => {
      setSync({ kind: 'syncing' })
      try {
        const r = await fetch('/api/policy/persona', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        if (!r.ok) throw new Error(`bridge ${r.status}`)
        const body = await r.json()
        setSync({
          kind: 'applied',
          at: Date.now(),
          label: body?.active?.label ?? payload.label,
        })
      } catch (e) {
        setSync({ kind: 'error', message: String((e as Error).message ?? e) })
      }
    }
    // On the very first effect tick, wait a bit longer so we don't slam the
    // bridge before the user has actually interacted — but still sync once so
    // the bridge reflects what the dashboard is showing.
    const delay = didInitialSync.current ? 300 : 600
    debounceRef.current = window.setTimeout(() => {
      didInitialSync.current = true
      void fire()
    }, delay)
    return () => {
      if (debounceRef.current != null) window.clearTimeout(debounceRef.current)
    }
  }, [activeExchange, activePersona, fee.roundTripTakerTaker, threshold])

  return (
    <section className="card fee-explorer">
      <div className="fee-explorer-header">
        <h2 style={{ margin: 0 }}>Fee persona explorer</h2>
        <span className="meta">
          Switch venues & VIP tiers to see how the v1.3 edge evaporates or widens.
          The bridge gates the premium lane against the active persona — try it live.
        </span>
        <SyncBadge sync={sync} />
      </div>

      {/* Exchange tabs */}
      <div className="fx-tabs">
        {EXCHANGE_ORDER.map(id => {
          const ex = EXCHANGE_FEE_MATRIX[id]
          return (
            <button
              key={id}
              className={`fx-tab ${id === activeId ? 'is-active' : ''} ${!ex.supportsDualQuoteArb ? 'is-disabled' : ''}`}
              onClick={() => setActiveId(id)}
            >
              <span className="fx-tab-name">{ex.name}</span>
              <span className="fx-tab-tagline">{ex.tagline}</span>
            </button>
          )
        })}
      </div>

      {/* Huge effective-fee headline */}
      <div className={`fx-headline ${profitable ? '' : 'is-unprofitable'}`}>
        <div className="fx-headline-primary">
          <div className="fx-headline-label">Effective round-trip fee (taker-taker)</div>
          <div className="fx-headline-value">
            {(fee.roundTripTakerTaker * 100).toFixed(4)}%
            <span className="fx-headline-bp">{feeBp.toFixed(1)} bp</span>
          </div>
        </div>
        <div className="fx-headline-sub">
          <div>
            <span className="fx-sub-label">maker</span>
            <span className="fx-sub-val">{(fee.maker * 100).toFixed(4)}%</span>
          </div>
          <div>
            <span className="fx-sub-label">taker</span>
            <span className="fx-sub-val">{(fee.taker * 100).toFixed(4)}%</span>
          </div>
          <div>
            <span className="fx-sub-label">r.t. mixed</span>
            <span className="fx-sub-val">{(fee.roundTripMixed * 100).toFixed(4)}%</span>
          </div>
          <div>
            <span className="fx-sub-label">r.t. maker-maker</span>
            <span className="fx-sub-val">{(fee.roundTripMakerMaker * 100).toFixed(4)}%</span>
          </div>
        </div>
        {fee.note && <div className="fx-headline-note">{fee.note}</div>}
      </div>

      {!activeExchange.supportsDualQuoteArb && (
        <div className="fx-structural-warning">
          <strong>Structurally incompatible:</strong> {activeExchange.structuralNote}
        </div>
      )}

      <div className="fx-grid">
        {/* VIP tier selector */}
        <div className="fx-panel">
          <div className="fx-panel-label">VIP tier</div>
          <div className="fx-radio-group">
            {activeExchange.vipTiers.map(t => (
              <label
                key={t.id}
                className={`fx-radio ${activePersona.vipTierId === t.id ? 'is-active' : ''}`}
              >
                <input
                  type="radio"
                  name={`vip-${activeId}`}
                  checked={activePersona.vipTierId === t.id}
                  onChange={() => setPersona(activeId, { vipTierId: t.id })}
                />
                <span className="fx-radio-name">{t.name}</span>
                <span className="fx-radio-gate">{t.volumeGate}</span>
                <span className="fx-radio-fees">
                  {(t.maker * 100).toFixed(3)}% / {(t.taker * 100).toFixed(3)}%
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Discount toggles */}
        <div className="fx-panel">
          <div className="fx-panel-label">Discounts / promotions</div>
          {activeExchange.discounts.length === 0 && (
            <div className="meta">No promos for this venue.</div>
          )}
          <div className="fx-check-group">
            {activeExchange.discounts.map(d => {
              const on = activePersona.discountIds.includes(d.id)
              return (
                <label
                  key={d.id}
                  className={`fx-check ${on ? 'is-active' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => {
                      const ids = new Set(activePersona.discountIds)
                      if (ids.has(d.id)) ids.delete(d.id)
                      else ids.add(d.id)
                      setPersona(activeId, { discountIds: Array.from(ids) })
                    }}
                  />
                  <div>
                    <div className="fx-check-label">{d.label}</div>
                    <div className="fx-check-desc">{d.description}</div>
                  </div>
                </label>
              )
            })}
          </div>
        </div>

        {/* Pair + threshold */}
        <div className="fx-panel">
          <div className="fx-panel-label">Pair & threshold</div>
          <div className="fx-row">
            <label className="fx-field">
              <span>Traded pair</span>
              <select
                value={activePersona.pair}
                onChange={e => setPersona(activeId, { pair: e.target.value })}
              >
                {V13_PAIRS.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
            <label className="fx-field">
              <span>Threshold (bp)</span>
              <input
                type="number"
                step={1}
                min={1}
                max={100}
                value={Math.round(thresholdBp)}
                onChange={e => {
                  const bp = Number(e.target.value)
                  if (!Number.isFinite(bp)) return
                  setThreshold(Math.max(0.0001, bp / 10000))
                }}
              />
            </label>
          </div>
        </div>
      </div>

      {/* Live metrics */}
      <div className={`fx-metrics ${profitable ? '' : 'is-unprofitable'}`}>
        <div className="fx-metric">
          <div className="fx-metric-label">Net edge after fees</div>
          <div className={`fx-metric-value ${profitable ? 'pos' : 'neg'}`}>
            {edgeBp.toFixed(1)} bp
          </div>
          <div className="fx-metric-sub">threshold − r.t. fee</div>
        </div>
        <div className="fx-metric">
          <div className="fx-metric-label">Break-even threshold</div>
          <div className="fx-metric-value">
            {(fee.roundTripTakerTaker * 100).toFixed(3)}%
          </div>
          <div className="fx-metric-sub">r.t. taker-taker floor</div>
        </div>
        <div className="fx-metric">
          <div className="fx-metric-label">Est. trades / coin / day</div>
          <div className="fx-metric-value">
            {activeExchange.supportsDualQuoteArb ? freq.tradesPerCoinPerDay.toFixed(1) : '—'}
          </div>
          <div className="fx-metric-sub">vs v1.3 baseline 12.0</div>
        </div>
        <div className="fx-metric">
          <div className="fx-metric-label">Est. NetPnL / day ({V13_COINS} coins)</div>
          <div className={`fx-metric-value ${pnl.daily > 0 ? 'pos' : 'neg'}`}>
            {activeExchange.supportsDualQuoteArb
              ? `$${pnl.daily.toFixed(2)}`
              : '—'}
          </div>
          <div className="fx-metric-sub">
            {activeExchange.supportsDualQuoteArb
              ? `$${pnl.perTrade.toFixed(4)} / trade · ${V13_NOTIONAL_USD} notional`
              : 'arb not available on this venue'}
          </div>
        </div>
      </div>

      <div className="fx-reasoning">{freq.reasoning}</div>
    </section>
  )
}

function SyncBadge({ sync }: { sync: SyncStatus }) {
  if (sync.kind === 'idle') {
    return <span className="fx-sync fx-sync-idle">bridge: idle</span>
  }
  if (sync.kind === 'syncing') {
    return <span className="fx-sync fx-sync-pending">bridge: syncing…</span>
  }
  if (sync.kind === 'applied') {
    const ago = Math.max(0, Math.floor((Date.now() - sync.at) / 1000))
    return (
      <span className="fx-sync fx-sync-applied" title={sync.label}>
        bridge: applied {ago < 2 ? 'just now' : `${ago}s ago`}
      </span>
    )
  }
  return (
    <span className="fx-sync fx-sync-error" title={sync.message}>
      bridge: offline
    </span>
  )
}
