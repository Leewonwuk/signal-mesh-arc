import { useEffect, useState } from 'react'
import { FeeExplorer } from './components/FeeExplorer'
import { AllocatorCard } from './components/AllocatorCard'
import { PolicyHeatmap } from './components/PolicyHeatmap'

interface Signal {
  producer_id: string
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
interface Tx { hash: string; amount: number; at: number }
interface Reliability {
  window: number
  reliability: Record<string, { hit_rate: number; samples: number; total_pnl: number }>
}
interface Health {
  ok: boolean
  signals: { raw: number; premium: number }
  tx_settled: number
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

  useEffect(() => {
    let alive = true
    const tick = async () => {
      const [h, r, p, t, rr] = await Promise.all([
        j<Health>('/health'),
        j<{ signals: Signal[] }>('/signals/latest'),
        j<{ signals: Signal[] }>('/signals/premium'),
        j<{ tx: Tx[] }>('/tx/recent'),
        j<Reliability>('/producer/reliability'),
      ])
      if (!alive) return
      setHealth(h)
      setRaw(r?.signals ?? [])
      setPremium(p?.signals ?? [])
      setTx(t?.tx ?? [])
      setRel(rr)
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  const producers = rel ? Object.entries(rel.reliability) : []

  return (
    <div className="app">
      <header>
        <h1>
          <span className="live-dot" /> Signal Mesh <span className="accent">on Arc</span>
        </h1>
        <p>Live agent-to-agent nanopayment marketplace — Arc testnet</p>
      </header>

      <div className="grid">
        <div className="stat">
          <div className="label">raw signals</div>
          <div className="value cyan">{health?.signals.raw ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">premium signals</div>
          <div className="value purple">{health?.signals.premium ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">on-chain tx</div>
          <div className="value green">{health?.tx_settled ?? '—'}</div>
        </div>
        <div className="stat">
          <div className="label">producers tracked</div>
          <div className="value amber">{producers.length || '—'}</div>
        </div>
      </div>

      <FeeExplorer />

      {/* Capital Allocator section — F6. Sits between FeeExplorer and the
          existing economics/tx feed. AllocatorCard is the full-width "what is
          the allocator doing right now?" card; PolicyHeatmap sits below it and
          shows the 9×7 Q-table visit matrix. */}
      <section className="allocator-section">
        <h2 className="section-heading">Capital Allocator</h2>
        <AllocatorCard />
        <PolicyHeatmap />
      </section>

      <div className="columns">
        <section className="card">
          <h2>Premium signal stream</h2>
          {premium.slice(-12).reverse().map((s, i) => (
            <div className="row" key={`${s.timestamp}-${i}`}>
              <span className="tag premium">premium</span>
              <span className="sym">{s.symbol}</span>
              <span className="meta">
                {s.action} · regime={s.regime ?? '—'} · conf={s.confidence_score?.toFixed(2) ?? '—'}
              </span>
              <span className="num">${s.expected_profit_usd?.toFixed(3) ?? '—'}</span>
            </div>
          ))}
          {premium.length === 0 && <div className="meta">waiting for meta_agent…</div>}
        </section>

        <section className="card">
          <h2>Producer reliability (last 200)</h2>
          {producers.length === 0 && <div className="meta">cold start — waiting for outcomes</div>}
          {producers.map(([pid, r]) => (
            <div className="row" key={pid}>
              <span className="sym" style={{ minWidth: 140 }}>{pid}</span>
              <div className="reliability-bar">
                <span style={{ width: `${(r.hit_rate * 100).toFixed(0)}%` }} />
              </div>
              <span className="num">{(r.hit_rate * 100).toFixed(0)}%</span>
              <span className="meta">n={r.samples}</span>
            </div>
          ))}
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
              >
                {t.hash.slice(0, 10)}…{t.hash.slice(-6)}
              </a>
              <span className="meta">{new Date(t.at).toLocaleTimeString()}</span>
              <span className="num">${t.amount.toFixed(4)}</span>
            </div>
          ))}
          {tx.length === 0 && <div className="meta">no on-chain tx yet</div>}
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <h2>Raw signal stream</h2>
        {raw.slice(-20).reverse().map((s, i) => (
          <div className="row" key={`${s.timestamp}-${i}`}>
            <span className="tag raw">raw</span>
            <span className="sym">{s.symbol}</span>
            <span className="meta">
              {s.producer_id} · {s.action} · premium={(s.premium_rate * 100).toFixed(3)}%
            </span>
            <span className="num">${(0.002).toFixed(3)}</span>
          </div>
        ))}
        {raw.length === 0 && <div className="meta">waiting for producers…</div>}
      </section>
    </div>
  )
}
