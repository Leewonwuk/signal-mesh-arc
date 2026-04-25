/**
 * Arc Bridge — AlphaLoop
 *
 * Routes:
 *   POST /signals/publish      — producers post raw signals (free, internal)
 *   GET  /signals/latest       — 402-paywalled (x402) — $0.002 per fetch (raw)
 *   GET  /signals/premium      — 402-paywalled (x402) — variable per fetch (meta)
 *   GET  /health               — liveness probe
 *   GET  /tx/recent            — recent on-chain settlement tx hashes (for dashboard)
 *   POST /tx/report            — executor reports a settled Arc tx hash
 *   POST /signals/outcome      — executor reports realized PnL per signal
 *   GET  /producer/reliability — per-producer hit-rate over the last N outcomes
 *   GET  /.well-known/agent-card/:role  — ERC-8004 registration-v1 card per wallet
 *   GET  /agent-cards/:role    — same as above, convenience alias
 */
import 'dotenv/config'
import express from 'express'
import type { Request, Response } from 'express'
import fs from 'node:fs'
import path from 'node:path'

const app = express()
app.use(express.json({ limit: '1mb' }))

// --- ERC-8004 agent-card serving --------------------------------------------
// Four wallet-specific registration-v1 JSON documents live at
// ../agent-cards/<role>.json. We expose them at both /.well-known/agent-card/
// (the canonical discovery path) and /agent-cards/ (a convenience alias the
// dashboard uses to deep-link from the "Agent identity" requirement badge).
const AGENT_CARDS_DIR = path.resolve(import.meta.dirname, '..', 'agent-cards')
const AGENT_CARD_ROLES = new Set([
  'producer-dual-quote',
  'producer-kimchi',
  'meta-agent',
  'executor-agent',
])
function serveAgentCard(req: Request, res: Response) {
  const role = String(req.params.role || '').replace(/\.json$/, '')
  if (!AGENT_CARD_ROLES.has(role)) {
    return res.status(404).json({ error: 'unknown agent role', valid: [...AGENT_CARD_ROLES] })
  }
  try {
    const body = fs.readFileSync(path.join(AGENT_CARDS_DIR, `${role}.json`), 'utf8')
    res.type('application/json').send(body)
  } catch (e) {
    res.status(500).json({ error: 'card not found on disk', detail: String(e) })
  }
}
app.get('/.well-known/agent-card/:role', serveAgentCard)
app.get('/agent-cards/:role', serveAgentCard)
app.get('/.well-known/agent-cards', (_req, res) => {
  res.json({
    cards: [...AGENT_CARD_ROLES].map(role => ({
      role,
      url: `/.well-known/agent-card/${role}`,
    })),
    spec: 'https://eips.ethereum.org/EIPS/eip-8004',
    project: 'AlphaLoop',
  })
})

// --- x402 paywall (optional; toggled by X402_ENABLED=1) ---------------------
// The x402 facilitator's default Coinbase server historically hardcodes
// `base-sepolia`. On Arc testnet, either (a) Circle exposes a compatible
// facilitator URL via FACILITATOR_URL, or (b) we run paywall-off for the demo
// and document it. Either way, the route handlers below are unchanged —
// middleware just gates access.
const PAYWALL_ON = process.env.X402_ENABLED === '1'
const RECIPIENT = process.env.PRODUCER_WALLET_ADDRESS ?? ''
const FACILITATOR_URL = process.env.FACILITATOR_URL ?? 'https://x402.org/facilitator'
const NETWORK = process.env.X402_NETWORK ?? 'arc-testnet'

if (PAYWALL_ON) {
  if (!RECIPIENT) {
    console.warn('[bridge] X402_ENABLED=1 but PRODUCER_WALLET_ADDRESS unset — disabling paywall')
  } else {
    try {
      // Lazy import so the bridge still boots if x402-express is unavailable
      const { paymentMiddleware } = await import('x402-express')
      app.use(
        paymentMiddleware(
          RECIPIENT as `0x${string}`,
          {
            'GET /signals/latest': { price: '$0.002', network: NETWORK },
            'GET /signals/premium': { price: '$0.01', network: NETWORK },
          },
          { url: FACILITATOR_URL }
        )
      )
      console.log(`[bridge] x402 paywall ON — recipient=${RECIPIENT} network=${NETWORK}`)
      console.log(`[bridge] facilitator=${FACILITATOR_URL}`)
    } catch (e) {
      console.error('[bridge] failed to load x402-express, paywall OFF:', e)
    }
  }
} else {
  console.log('[bridge] x402 paywall OFF (set X402_ENABLED=1 to enable)')
}

// In-memory signal store (demo scope — swap for Redis in prod)
interface StoredSignal {
  producer_id: string
  strategy: string
  symbol: string
  action: string
  premium_rate: number
  tier: string
  reason: string
  timestamp: number
  received_at: number
  [k: string]: unknown
}
const raw: StoredSignal[] = []
const premium: StoredSignal[] = []
const recentTx: { hash: string; amount: number; at: number }[] = []

// Outcome feedback: per-producer running hit-rate so the meta agent can price
// conflict resolution against realized performance (Karpathy loop).
// `realized_edge_rate`, `notional_usd`, `price_paid_usdc`, `entry_premium` are
// the post-Overdeck-fix fields that let us distinguish "producer wrong" from
// "executor overpaid" when a signal ends red.
interface Outcome {
  producer_id: string
  symbol: string
  action: string
  signal_ts: number
  pnl_usd: number
  hit: boolean
  at: number
  realized_edge_rate?: number
  notional_usd?: number
  price_paid_usdc?: number
  entry_premium?: number
}
const outcomes: Outcome[] = []
const RELIABILITY_WINDOW = 200

// ── Capital Allocator RL state (F4) ────────────────────────────────────
// The allocator agent posts its current 8h allocation decision here; the
// dashboard + executor poll it. Producers post realized 8h NetPnL per
// strategy to /strategy/tick_pnl so the allocator can compute reward
// offline (no dependency on /signals/outcome — avoids circular reward).
interface AllocationWeights {
  v1: number
  v2: number
  v3: number
}
interface AllocationEntry {
  tick_id: string
  ts: string
  state_idx: number
  action_idx: number
  action_label: string
  weights: AllocationWeights
  q_values: number[]
  persona_id?: string
  received_at: number
  // Design §7.2 + §5.6 optional enrichments — passed through verbatim
  state_label?: string
  q_value_second_best?: number
  exploration_bonus?: number
  ucb_score?: number
  regime_features?: Record<string, number>
  drift_downsize?: { v1?: number; v2?: number; v3?: number }
  allocation_frozen?: boolean
  frozen_reason?: string | null
  v3_entry_offset_sec?: number
  cadence_seconds?: number
  next_tick_at?: number
  pretrained?: boolean
  notional_scalar?: number
}
interface TickPnlEntry {
  tick_id: string
  strategy: 'v1' | 'v2' | 'v3'
  ts: string
  realized_pnl_usd: number
  notional_usd: number
  n_trades: number
  regime_snapshot?: Record<string, unknown>
  received_at: number
}
const allocationLog: AllocationEntry[] = []
const ALLOCATION_CAP = 500
const tickPnlLog: TickPnlEntry[] = []
const TICK_PNL_CAP = 500
const STRATEGY_PNL_WINDOW_MS = 90 * 60 * 1000 // 90-minute rolling window

// ── Active pricing persona ─────────────────────────────────────────────
// Set live from the dashboard's Fee Persona Explorer. The bridge uses it
// to tier incoming signals (premium vs raw) and to compute /economics/summary.
// Default is the compile-time baseline the Q-table was pretrained against.
interface ActivePersona {
  exchangeId: string
  label: string
  feeRoundTrip: number          // decimal (0.001 = 0.10%)
  thresholdRate: number         // decimal; premium floor for tier promotion
  supportsDualQuoteArb: boolean
  updatedAt: number
  source: 'default' | 'dashboard'
}
const DEFAULT_PERSONA: ActivePersona = {
  exchangeId: 'bybit',
  label: 'Bybit VIP 0 + USDC taker promo',
  feeRoundTrip: 0.001,
  thresholdRate: 0.0017,
  supportsDualQuoteArb: true,
  updatedAt: Date.now(),
  source: 'default',
}
let activePersona: ActivePersona = { ...DEFAULT_PERSONA }
let personaDemotions = { arb_incompatible: 0, below_threshold: 0 }

app.get('/policy/persona', (_req, res) => {
  res.json({ active: activePersona, demotions: personaDemotions })
})

app.post('/policy/persona', (req: Request, res: Response) => {
  const p = req.body as Partial<ActivePersona>
  if (typeof p.feeRoundTrip !== 'number' || p.feeRoundTrip < 0) {
    return res.status(400).json({ error: 'missing or invalid feeRoundTrip' })
  }
  activePersona = {
    exchangeId: p.exchangeId ?? 'custom',
    label: p.label ?? 'custom',
    feeRoundTrip: p.feeRoundTrip,
    // If the caller didn't supply a thresholdRate, fall back to "fee + 7bp"
    // — the same razor-thin margin v1.3 prod runs at over Binance VIP0.
    thresholdRate: typeof p.thresholdRate === 'number' && p.thresholdRate > 0
      ? p.thresholdRate
      : p.feeRoundTrip + 0.0007,
    supportsDualQuoteArb: p.supportsDualQuoteArb !== false,
    updatedAt: Date.now(),
    source: 'dashboard',
  }
  // Reset counters so the demo can visibly see "since this persona was
  // applied, how many signals got demoted?" without prior state polluting.
  personaDemotions = { arb_incompatible: 0, below_threshold: 0 }
  console.log(
    `[bridge] persona <- ${activePersona.label} ` +
    `rt=${(activePersona.feeRoundTrip * 100).toFixed(3)}% ` +
    `th=${(activePersona.thresholdRate * 100).toFixed(3)}% ` +
    `arb=${activePersona.supportsDualQuoteArb}`,
  )
  return res.json({ ok: true, active: activePersona })
})

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    signals: { raw: raw.length, premium: premium.length },
    tx_settled: recentTx.length,
  })
})

app.post('/signals/publish', (req: Request, res: Response) => {
  const s = req.body as StoredSignal
  if (!s.producer_id || !s.action) {
    return res.status(400).json({ error: 'missing producer_id or action' })
  }
  // Persona-aware tier gating. Producers publish with their own tier hint, but
  // the bridge re-evaluates against the active fee persona so a judge flipping
  // to "Coinbase (no alt/USDT pairs)" or "MEXC (0.05% r.t.)" sees the premium
  // lane respond live without restarting producers.
  let finalTier: string = s.tier ?? 'raw'
  let demotionReason: string | null = null
  if (!activePersona.supportsDualQuoteArb) {
    finalTier = 'raw'
    demotionReason = 'arb_incompatible'
    personaDemotions.arb_incompatible += 1
  } else if (s.tier === 'premium') {
    const prem = typeof s.premium_rate === 'number' ? Math.abs(s.premium_rate) : 0
    if (prem > 0 && prem < activePersona.thresholdRate) {
      finalTier = 'raw'
      demotionReason = 'below_threshold'
      personaDemotions.below_threshold += 1
    }
  }
  const enriched: StoredSignal = {
    ...s,
    tier: finalTier,
    received_at: Date.now(),
  }
  if (demotionReason) enriched.demoted_reason = demotionReason

  if (finalTier === 'premium') premium.push(enriched)
  else raw.push(enriched)

  // Trim to last 500
  if (raw.length > 500) raw.splice(0, raw.length - 500)
  if (premium.length > 500) premium.splice(0, premium.length - 500)

  return res.json({ ok: true, stored: finalTier, demoted_reason: demotionReason })
})

app.get('/signals/latest', (_req, res) => {
  const latest = raw.slice(-10)
  res.json({ signals: latest, tier: 'raw', price_usdc: 0.002 })
})

app.get('/signals/premium', (_req, res) => {
  const latest = premium.slice(-10)
  res.json({ signals: latest, tier: 'premium', price_usdc: 0.01 })
})

app.get('/tx/recent', (_req, res) => {
  res.json({ tx: recentTx.slice(-50) })
})

app.post('/tx/report', (req: Request, res: Response) => {
  const { hash, amount } = req.body as { hash?: string; amount?: number }
  if (!hash) return res.status(400).json({ error: 'missing hash' })
  recentTx.push({ hash, amount: amount ?? 0, at: Date.now() })
  if (recentTx.length > 200) recentTx.splice(0, recentTx.length - 200)
  console.log(`[bridge] tx reported: ${hash} ($${amount ?? 0})`)
  return res.json({ ok: true, count: recentTx.length })
})

app.post('/signals/outcome', (req: Request, res: Response) => {
  const o = req.body as Partial<Outcome>
  if (!o.producer_id || typeof o.pnl_usd !== 'number') {
    return res.status(400).json({ error: 'missing producer_id or pnl_usd' })
  }
  outcomes.push({
    producer_id: o.producer_id,
    symbol: o.symbol ?? 'UNK',
    action: o.action ?? 'UNK',
    signal_ts: o.signal_ts ?? 0,
    pnl_usd: o.pnl_usd,
    hit: o.pnl_usd > 0,
    at: Date.now(),
    realized_edge_rate: o.realized_edge_rate,
    notional_usd: o.notional_usd,
    price_paid_usdc: o.price_paid_usdc,
    entry_premium: o.entry_premium,
  })
  if (outcomes.length > 5000) outcomes.splice(0, outcomes.length - 5000)
  return res.json({ ok: true, count: outcomes.length })
})

// Aggregate economics surface — the dashboard pulls this to show the "are we
// actually net-positive after fees + what we paid for signals?" headline.
app.get('/economics/summary', (_req, res) => {
  const recent = outcomes.slice(-RELIABILITY_WINDOW)
  let netPnl = 0
  let gross = 0
  let fees = 0
  let paid = 0
  let n = 0
  const feeRt = activePersona.feeRoundTrip
  for (const o of recent) {
    netPnl += o.pnl_usd
    if (typeof o.realized_edge_rate === 'number' && typeof o.notional_usd === 'number') {
      gross += o.realized_edge_rate * o.notional_usd
      fees += feeRt * o.notional_usd
    }
    if (typeof o.price_paid_usdc === 'number') paid += o.price_paid_usdc
    n += 1
  }
  // Allocator RL additions: let the dashboard headline surface "how many
  // ticks has the allocator decided" + rolling per-strategy PnL so the
  // Policy Heatmap card doesn't need a second round-trip.
  const latest = allocationLog.length > 0 ? allocationLog[allocationLog.length - 1] : null
  const latest_allocation = latest
    ? { action_label: latest.action_label, weights: latest.weights }
    : null
  const cutoff = Date.now() - STRATEGY_PNL_WINDOW_MS
  const strategy_pnl_90m: AllocationWeights = { v1: 0, v2: 0, v3: 0 }
  for (const e of tickPnlLog) {
    if (e.received_at >= cutoff) {
      strategy_pnl_90m[e.strategy] += e.realized_pnl_usd
    }
  }
  strategy_pnl_90m.v1 = Number(strategy_pnl_90m.v1.toFixed(4))
  strategy_pnl_90m.v2 = Number(strategy_pnl_90m.v2.toFixed(4))
  strategy_pnl_90m.v3 = Number(strategy_pnl_90m.v3.toFixed(4))
  res.json({
    window: RELIABILITY_WINDOW,
    samples: n,
    net_pnl_cumulative: Number(netPnl.toFixed(4)),
    gross_pnl: Number(gross.toFixed(4)),
    fees_paid: Number(fees.toFixed(4)),
    paid_to_producers: Number(paid.toFixed(4)),
    fee_persona: activePersona.label,
    fee_persona_id: activePersona.exchangeId,
    fee_round_trip: activePersona.feeRoundTrip,
    threshold_rate: activePersona.thresholdRate,
    supports_dual_quote_arb: activePersona.supportsDualQuoteArb,
    persona_source: activePersona.source,
    demotions: personaDemotions,
    allocation_count: allocationLog.length,
    latest_allocation,
    strategy_pnl_90m,
  })
})

app.get('/producer/reliability', (_req, res) => {
  const recent = outcomes.slice(-RELIABILITY_WINDOW)
  const byProducer = new Map<string, { n: number; hits: number; pnl: number }>()
  for (const o of recent) {
    const agg = byProducer.get(o.producer_id) ?? { n: 0, hits: 0, pnl: 0 }
    agg.n += 1
    if (o.hit) agg.hits += 1
    agg.pnl += o.pnl_usd
    byProducer.set(o.producer_id, agg)
  }
  const reliability: Record<string, { hit_rate: number; samples: number; total_pnl: number }> = {}
  for (const [k, v] of byProducer.entries()) {
    reliability[k] = {
      hit_rate: v.n > 0 ? v.hits / v.n : 0,
      samples: v.n,
      total_pnl: v.pnl,
    }
  }
  res.json({ window: RELIABILITY_WINDOW, reliability })
})

// ── /allocation — allocator agent publishes its current decision ───────
app.post('/allocation', (req: Request, res: Response) => {
  const a = req.body as Partial<AllocationEntry>
  if (
    typeof a.tick_id !== 'string' ||
    typeof a.ts !== 'string' ||
    typeof a.state_idx !== 'number' ||
    typeof a.action_idx !== 'number' ||
    typeof a.action_label !== 'string' ||
    !a.weights ||
    typeof a.weights.v1 !== 'number' ||
    typeof a.weights.v2 !== 'number' ||
    typeof a.weights.v3 !== 'number' ||
    !Array.isArray(a.q_values)
  ) {
    return res.status(400).json({ error: 'missing or malformed fields' })
  }
  if (a.state_idx < 0 || a.state_idx > 8) {
    return res.status(400).json({ error: 'state_idx out of range [0,8]' })
  }
  if (a.action_idx < 0 || a.action_idx > 6) {
    return res.status(400).json({ error: 'action_idx out of range [0,6]' })
  }
  if (a.q_values.length !== 7) {
    return res.status(400).json({ error: 'q_values must have length 7' })
  }
  const wSum = a.weights.v1 + a.weights.v2 + a.weights.v3
  if (wSum < 0.99 || wSum > 1.01) {
    return res
      .status(400)
      .json({ error: `weights sum ${wSum.toFixed(4)} outside [0.99, 1.01]` })
  }
  const entry: AllocationEntry = {
    tick_id: a.tick_id,
    ts: a.ts,
    state_idx: a.state_idx,
    action_idx: a.action_idx,
    action_label: a.action_label,
    weights: { v1: a.weights.v1, v2: a.weights.v2, v3: a.weights.v3 },
    q_values: a.q_values as number[],
    persona_id: a.persona_id,
    received_at: Date.now(),
    // §7.2 + §5.6 pass-through (undefined-safe)
    state_label: a.state_label,
    q_value_second_best: a.q_value_second_best,
    exploration_bonus: a.exploration_bonus,
    ucb_score: a.ucb_score,
    regime_features: a.regime_features,
    drift_downsize: a.drift_downsize,
    allocation_frozen: a.allocation_frozen,
    frozen_reason: a.frozen_reason,
    v3_entry_offset_sec: a.v3_entry_offset_sec,
    cadence_seconds: a.cadence_seconds,
    next_tick_at: a.next_tick_at,
    pretrained: a.pretrained,
    notional_scalar: a.notional_scalar,
  }
  allocationLog.push(entry)
  if (allocationLog.length > ALLOCATION_CAP) {
    allocationLog.splice(0, allocationLog.length - ALLOCATION_CAP)
  }
  return res.json({ ok: true, tick_id: entry.tick_id })
})

app.get('/allocation', (_req, res) => {
  if (allocationLog.length === 0) return res.json({ tick_id: null })
  return res.json(allocationLog[allocationLog.length - 1])
})

app.get('/allocation/history', (req: Request, res: Response) => {
  const rawLimit = parseInt((req.query.limit as string | undefined) ?? '50', 10)
  const limit = Number.isFinite(rawLimit)
    ? Math.max(1, Math.min(ALLOCATION_CAP, rawLimit))
    : 50
  const entries = allocationLog.slice(-limit)
  return res.json({ entries, count: entries.length })
})

// ── /strategy/tick_pnl — producer reports 8h realized NetPnL ───────────
app.post('/strategy/tick_pnl', (req: Request, res: Response) => {
  const t = req.body as Partial<TickPnlEntry>
  if (
    typeof t.tick_id !== 'string' ||
    typeof t.ts !== 'string' ||
    typeof t.realized_pnl_usd !== 'number' ||
    typeof t.notional_usd !== 'number' ||
    typeof t.n_trades !== 'number'
  ) {
    return res.status(400).json({ error: 'missing or malformed fields' })
  }
  if (t.strategy !== 'v1' && t.strategy !== 'v2' && t.strategy !== 'v3') {
    return res.status(400).json({ error: 'strategy must be v1|v2|v3' })
  }
  // De-dupe on (tick_id, strategy): replace prior entry so reward is idempotent.
  const existing = tickPnlLog.findIndex(
    (e) => e.tick_id === t.tick_id && e.strategy === t.strategy,
  )
  const entry: TickPnlEntry = {
    tick_id: t.tick_id,
    strategy: t.strategy,
    ts: t.ts,
    realized_pnl_usd: t.realized_pnl_usd,
    notional_usd: t.notional_usd,
    n_trades: t.n_trades,
    regime_snapshot: t.regime_snapshot,
    received_at: Date.now(),
  }
  if (existing >= 0) {
    tickPnlLog[existing] = entry
  } else {
    tickPnlLog.push(entry)
    if (tickPnlLog.length > TICK_PNL_CAP) {
      tickPnlLog.splice(0, tickPnlLog.length - TICK_PNL_CAP)
    }
  }
  return res.json({ ok: true })
})

app.get('/strategy/tick_pnl', (req: Request, res: Response) => {
  const tick_id = req.query.tick_id as string | undefined
  if (!tick_id) return res.status(400).json({ error: 'missing tick_id' })
  const entries: { v1?: TickPnlEntry; v2?: TickPnlEntry; v3?: TickPnlEntry } = {}
  for (const e of tickPnlLog) {
    if (e.tick_id === tick_id) entries[e.strategy] = e
  }
  const complete = !!(entries.v1 && entries.v2 && entries.v3)
  return res.json({ tick_id, entries, complete })
})

const PORT = parseInt(process.env.PORT ?? '3000', 10)
app.listen(PORT, () => {
  console.log(`[bridge] listening on http://localhost:${PORT}`)
  console.log(`[bridge] signals stored in-memory. Use /signals/publish to feed.`)
})
