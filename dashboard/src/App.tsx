import { useEffect, useMemo, useRef, useState } from 'react'
import { FeeExplorer } from './components/FeeExplorer'
import { AllocatorCard } from './components/AllocatorCard'
import { PolicyHeatmap } from './components/PolicyHeatmap'
import { RequirementsBadge } from './components/RequirementsBadge'
import { ProductionAnchor } from './components/ProductionAnchor'
import { WhyArcCard } from './components/WhyArcCard'
import { FeeMatrix } from './components/FeeMatrix'
import { AgentIdentityCard } from './components/AgentIdentityCard'
import { EXCHANGE_SCOPES, findScope, scopeThresholdDecimal } from './lib/exchange_scopes'
import { strategyMeta, countByStrategy, type StrategyId } from './lib/strategy_meta'
import { StrategyCards } from './components/StrategyCards'
import { RegimeMap } from './components/RegimeMap'

interface Signal {
  producer_id: string
  strategy?: string
  symbol: string
  action: string
  premium_rate: number
  tier: string
  confidence_score?: number
  notional_usd?: number
  expected_profit_usd?: number
  regime?: string
  timestamp: number
}
interface Tx { hash: string; amount: number; at: number; src_label?: string; dst_label?: string }
interface Reliability {
  window: number
  reliability: Record<string, { hit_rate: number; samples: number; total_pnl: number }>
}
interface Health {
  ok: boolean
  signals: { raw: number; premium: number }
  tx_settled: number
}
interface Economics {
  samples: number
  net_pnl_cumulative: number
  paid_to_producers: number
  fee_persona: string
  demotions: { arb_incompatible: number; below_threshold: number }
}

async function j<T>(p: string): Promise<T | null> {
  try {
    const r = await fetch(`/api${p}`)
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [raw, setRaw] = useState<Signal[]>([])
  const [premium, setPremium] = useState<Signal[]>([])
  const [tx, setTx] = useState<Tx[]>([])
  const [rel, setRel] = useState<Reliability | null>(null)
  const [econ, setEcon] = useState<Economics | null>(null)
  const [lastUpdate, setLastUpdate] = useState<number>(0)
  // 5s after mount, if /api/health has never returned, we're on the public
  // Vercel build with no bridge reachable. Show a scaffold disclosure so a
  // judge clicking signal-mesh.vercel.app doesn't think the product is
  // broken — the live feed lives behind the local bridge in the video.
  const [scaffoldMode, setScaffoldMode] = useState(false)
  // Ref so the scaffold timer reads the live connection state, not the
  // lastUpdate value captured when the effect mounted. Without this, a
  // successful first tick at ~4.9s still triggers scaffold=true at 5s
  // because the timer closure saw lastUpdate=0 — a visible flash on the
  // deployed URL.
  const hasEverConnectedRef = useRef(false)
  // Exchange scope — top-level filter. Defaults to Binance because it's the
  // only tab backed by a live REST feed. Switching tabs reshapes what counts
  // as "premium" in the signal feeds below (threshold = fees + 0.02% buffer).
  const [scopeId, setScopeId] = useState<string>(EXCHANGE_SCOPES[0].id)
  const scope = useMemo(() => findScope(scopeId), [scopeId])
  const scopeThreshold = scopeThresholdDecimal(scope)

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const [h, r, p, t, rr, e] = await Promise.all([
        j<Health>('/health'),
        j<{ signals: Signal[] }>('/signals/latest'),
        j<{ signals: Signal[] }>('/signals/premium'),
        j<{ tx: Tx[] }>('/tx/recent'),
        j<Reliability>('/producer/reliability'),
        j<Economics>('/economics/summary'),
      ])
      if (!alive) return
      setHealth(h)
      setRaw(r?.signals ?? [])
      setPremium(p?.signals ?? [])
      setTx(t?.tx ?? [])
      if (rr) setRel(rr)
      if (e) setEcon(e)
      if (h) {
        setLastUpdate(Date.now())
        hasEverConnectedRef.current = true
      }
    }
    tick()
    const id = setInterval(tick, 1500)
    const scaffoldTimer = window.setTimeout(() => {
      if (alive && !hasEverConnectedRef.current) {
        setScaffoldMode(true)
      }
    }, 5000)
    return () => {
      alive = false
      clearInterval(id)
      window.clearTimeout(scaffoldTimer)
    }
  }, [])

  // If a successful tick lands after the timer already fired, clear scaffold mode.
  useEffect(() => {
    if (lastUpdate > 0 && scaffoldMode) setScaffoldMode(false)
  }, [lastUpdate, scaffoldMode])

  const producers = rel ? Object.entries(rel.reliability) : []
  const staleSec = lastUpdate ? Math.floor((Date.now() - lastUpdate) / 1000) : 0
  const stale = staleSec > 6

  // Per-strategy counts for the stream-header chips. The pitch is a 3-strategy
  // mesh (v1 kimchi · v2 dual · v3 funding); without this surface, judges can
  // only read the producer_id in each row and reasonably conclude "one strategy
  // running" — which misrepresents what the pipeline is actually doing.
  // Cadences differ wildly (v2 ~1s, v1 ~5-10s, v3 ~30s) so counts are the
  // honest presentation: each strategy's observed rate, not cosmetic parity.
  const rawCounts = useMemo(() => countByStrategy(raw), [raw])
  const premiumCounts = useMemo(() => countByStrategy(premium), [premium])

  // Per-strategy signal buckets for the StrategyCards grid. Each lane renders
  // in its own card with its own threshold semantics — see
  // components/StrategyCards.tsx for why unifying gates is dishonest.
  const v1Signals = useMemo(() => raw.filter(s => strategyMeta(s.strategy).id === 'v1'), [raw])
  const v2Signals = useMemo(() => raw.filter(s => strategyMeta(s.strategy).id === 'v2'), [raw])
  const v3Signals = useMemo(() => raw.filter(s => strategyMeta(s.strategy).id === 'v3'), [raw])

  return (
    <div className="app">
      <header>
        <h1>
          <span className="live-dot" /> <span className="accent">Alpha</span>Loop
        </h1>
        <p>
          The agent-to-agent alpha loop on Arc — learned Q-policy closes the payment loop,
          fed by a live v1.3 production arb bot
          {lastUpdate > 0 && (
            <span className={stale ? 'meta stale' : 'meta'} style={{ marginLeft: 12 }}>
              {stale ? `⚠ bridge reconnecting… (${staleSec}s)` : `updated ${staleSec}s ago`}
            </span>
          )}
        </p>
      </header>

      {scaffoldMode && (
        <div className="scaffold-banner">
          <span className="scaffold-icon">⚠</span>
          <div>
            <strong>Static demo scaffold.</strong> The live agent marketplace runs on the
            submitter's local bridge (producers → meta → executor → Arc testnet).
            Watch the <strong>pitch video</strong> for the real-time feed, heatmap, and
            60 variably-priced settlements landing on chain. The UI shell below is
            the same one used during recording; on this public deploy it will show
            placeholder counters until connected to a bridge.
          </div>
        </div>
      )}

      <RequirementsBadge txSettled={health?.tx_settled ?? null} />
      <ProductionAnchor />
      <WhyArcCard />

      <div className="grid">
        <div className="stat">
          <div className="label">raw signals</div>
          <div className="value cyan">{health?.signals?.raw ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">premium signals</div>
          <div className="value purple">{health?.signals?.premium ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">on-chain tx</div>
          <div className="value green">{health?.tx_settled ?? '—'}</div>
        </div>
        <div
          className="stat"
          title={
            econ && econ.samples < 30
              ? `demo window · n=${econ.samples} trades · law-of-large-numbers not yet engaged.\n` +
                `threshold > fee guarantees +EV (expected value), not +PnL per trade.\n` +
                `see SUBMISSION §11.b for 90d walk-forward backtest.`
              : 'cumulative net PnL = gross - trading fees - producer pay'
          }
        >
          <div className="label">net PnL (USDC)</div>
          <div className={`value ${(econ?.net_pnl_cumulative ?? 0) >= 0 ? 'green' : 'red'}`}>
            {econ ? econ.net_pnl_cumulative.toFixed(3) : '—'}
          </div>
          {econ && (
            <div className="stat-sublabel">
              n={econ.samples} trades · {econ.samples < 30 ? 'demo variance' : 'live window'}
            </div>
          )}
        </div>
        <div className="stat">
          <div className="label">persona demotions</div>
          <div className="value amber">
            {econ ? (econ.demotions.arb_incompatible + econ.demotions.below_threshold) : '—'}
          </div>
        </div>
        <div className="stat">
          <div className="label">producers tracked</div>
          <div className="value amber">{producers.length || '—'}</div>
        </div>
      </div>

      {/* Capital Allocator section — hero of the pitch. Lifted above FeeExplorer
          so the RL story lands in the first viewport fold at 1080p
          (was: FeeExplorer → Allocator → long scroll).
          RegimeMap is the wedge — answers "why three strategies?" before
          the AllocatorCard shows live state, so judges grasp the narrative
          before the numbers. */}
      <section className="allocator-section">
        <h2 className="section-heading">Capital Allocator · Q-learning (Reinforcement Learning)</h2>
        <RegimeMap />
        <AllocatorCard />
        <PolicyHeatmap />
      </section>

      {/* Per-strategy lanes — each with its own threshold basis. ExchangeScopeTabs
          is rendered inside the v2 card (its venue context only). */}
      <StrategyCards
        v1Signals={v1Signals}
        v2Signals={v2Signals}
        v3Signals={v3Signals}
        v2Scope={scope}
        v2ScopeId={scopeId}
        onV2ScopeChange={setScopeId}
        v2Threshold={scopeThreshold}
      />

      <FeeExplorer />

      {/* No scope props: the matrix is a global per-venue retail-default view.
          The previous "active scope" footer (driven by v2 ExchangeScopeTabs)
          conflicted with the FeePersonaExplorer's independent venue selector
          and produced contradictory captures during pre-recording review
          (Bybit shown in Explorer + Binance 0.17% in matrix footer). */}
      <FeeMatrix signals={raw} />

      <AgentIdentityCard />

      <div className="columns">
        <section className="card">
          <h2>
            Premium signal stream
            <span className="card-scope-chip">mesh overview · all lanes</span>
            <StrategyMixChip counts={premiumCounts} />
          </h2>
          {premium.slice(-12).reverse().map((s, i) => {
            const meta = strategyMeta(s.strategy)
            return (
              <div className="row" key={`${s.timestamp}-${i}`}>
                <span className={`strategy-chip strategy-${meta.cssId}`} title={meta.longLabel}>
                  {meta.id}·{meta.label}
                </span>
                <span className="tag premium">premium</span>
                <span className="sym">{s.symbol}</span>
                <span className="meta">
                  {s.action} · regime={s.regime ?? '—'} · conf={s.confidence_score?.toFixed(2) ?? '—'}
                </span>
                <span className="num">${s.expected_profit_usd?.toFixed(3) ?? '—'}</span>
              </div>
            )
          })}
          {premium.length === 0 && (
            <div className="meta">waiting for meta_agent…</div>
          )}
        </section>

        <section className="card">
          <h2>
            Meta-layer reliability
            <span className="card-scope-chip" title="hit-rate is computed at the meta_agent promotion boundary, not at the upstream producer level">
              promoted-signal scope
            </span>
          </h2>
          <div className="meta" style={{ marginBottom: 8, fontSize: 11 }}>
            Hit-rate over last 200 promoted (premium-tier) signals. Upstream per-producer
            tracking — kimchi · dual_quote · funding — is computed in the bridge but not
            yet fanned out per-producer (queued behind submission). Reliability stabilises
            after n≥200; cold-start n is noisy.
          </div>
          {producers.length === 0 && <div className="meta">cold start — waiting for outcomes</div>}
          {producers.map(([pid, r]) => {
            const samples = r?.samples ?? 0
            const isWarmup = samples < 50
            return (
              <div className="row" key={pid}>
                <span className="sym" style={{ minWidth: 140 }}>{pid}</span>
                <div className="reliability-bar">
                  <span style={{ width: `${((r?.hit_rate ?? 0) * 100).toFixed(0)}%` }} />
                </div>
                <span className="num">{((r?.hit_rate ?? 0) * 100).toFixed(0)}%</span>
                <span className="meta">
                  n={samples}
                  {isWarmup && <span style={{ color: '#fbbf24', marginLeft: 6 }}>· warmup</span>}
                </span>
              </div>
            )
          })}
        </section>

        <section className="card">
          <h2>Settlement tx (Arc testnet)</h2>
          {tx.slice(-12).reverse().map((t, i) => (
            <div className="row" key={`${t.hash}-${i}`}>
              <a
                className="tx-link"
                href={`https://testnet.arcscan.app/tx/${t.hash}`}
                target="_blank"
                rel="noreferrer"
                title={t.hash}
              >
                {t.hash.slice(0, 10)}…{t.hash.slice(-6)}
              </a>
              {(t.src_label || t.dst_label) && (
                <span className="meta">
                  {t.src_label ?? '?'} → {t.dst_label ?? '?'}
                </span>
              )}
              <span className="meta">{new Date(t.at).toLocaleTimeString()}</span>
              <span className="num">${(Number(t.amount) || 0).toFixed(4)}</span>
            </div>
          ))}
          {tx.length === 0 && <div className="meta">no on-chain tx yet</div>}
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>
          Raw signal stream
          <span className="card-scope-chip">mesh overview · all lanes</span>
          <StrategyMixChip counts={rawCounts} />
        </h2>
        {raw.slice(-20).reverse().map((s, i) => {
          const meta = strategyMeta(s.strategy)
          return (
            <div className="row" key={`${s.timestamp}-${i}`}>
              <span className={`strategy-chip strategy-${meta.cssId}`} title={meta.longLabel}>
                {meta.id}·{meta.label}
              </span>
              <span className="tag raw">raw</span>
              <span className="sym">{s.symbol}</span>
              <span className="meta">
                {s.producer_id} · {s.action} · premium={(s.premium_rate * 100).toFixed(3)}%
              </span>
              <span className="num">
                {s.expected_profit_usd != null ? `$${s.expected_profit_usd.toFixed(4)}` : '—'}
              </span>
            </div>
          )
        })}
        {raw.length === 0 && (
          <div className="meta">waiting for producers…</div>
        )}
      </section>
    </div>
  )
}

// Small inline chip that summarises how many v1/v2/v3 signals are in view.
// This is the "mesh proof" — without it the judge sees only producer_ids and
// can't tell at a glance that three strategies are truly interleaved.
// Zero-count strategies are rendered muted (not hidden) so the absence itself
// is honest ("v3 cadence is 30s — it's sparser, not missing").
function StrategyMixChip({ counts }: { counts: Record<StrategyId, number> }) {
  const total = counts.v1 + counts.v2 + counts.v3 + counts.unk
  if (total === 0) return null
  return (
    <span
      className="strategy-mix-chip"
      title="per-strategy counts in this view (v1·kimchi / v2·dual / v3·funding / ?·legacy unlabeled)"
    >
      mix&nbsp;
      <span className={`strategy-mix-seg v1 ${counts.v1 ? '' : 'is-zero'}`}>v1·{counts.v1}</span>
      <span className={`strategy-mix-seg v2 ${counts.v2 ? '' : 'is-zero'}`}>v2·{counts.v2}</span>
      <span className={`strategy-mix-seg v3 ${counts.v3 ? '' : 'is-zero'}`}>v3·{counts.v3}</span>
      {counts.unk > 0 && (
        <span
          className="strategy-mix-seg unk"
          title="signals with no/unrecognized strategy field — surfaces stale or mislabeled rows"
        >
          ?·{counts.unk}
        </span>
      )}
    </span>
  )
}
