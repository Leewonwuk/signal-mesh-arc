/**
 * ExchangeScopeTabs — top-level signal-filter tab strip.
 *
 * Renders four exchange tabs (Binance LIVE, Bybit, OKX, MEXC). Clicking a
 * tab changes the "scope" context: all signal streams below (Raw, Premium,
 * FeeMatrix) re-filter against that exchange's break-even threshold
 * (fees + 0.02% buffer). Each exchange has its own retail-persona-based
 * threshold so the dashboard reflects what a retail operator on THAT venue
 * would actually profit from.
 *
 * HONESTY NOTE
 * ------------
 * Only Binance is wired to a live REST feed (producers/dual_quote_agent
 * pulls real Binance BookTicker). The other three tabs filter the SAME
 * Binance-sourced stream through their own fee envelope — we surface what
 * WOULD settle if each venue's REST were also connected. The disclosure
 * banner under the tabs states this explicitly.
 *
 * Tab order
 * ---------
 * Binance first because it's the live feed. Bybit second because it's the
 * headlined persona in SUBMISSION.md (USDC-promo retail accessibility, #2
 * global volume, Circle partner). OKX/MEXC trail for fee-curve breadth.
 */
import { EXCHANGE_SCOPES, type ExchangeScope } from '../lib/exchange_scopes'

interface Props {
  activeId: string
  onSelect: (id: string) => void
}

export function ExchangeScopeTabs({ activeId, onSelect }: Props) {
  const active = EXCHANGE_SCOPES.find(s => s.id === activeId) ?? EXCHANGE_SCOPES[0]

  return (
    <section className="scope-tabs-section">
      <div className="scope-tabs-header">
        <div className="scope-tabs-eyebrow">Signal scope — per-exchange retail break-even</div>
        <div className="scope-tabs-note">
          Each tab re-filters the feed against that venue's fee envelope (VIP0 + retail promo).
        </div>
      </div>

      <div className="scope-tabs-row" role="tablist">
        {EXCHANGE_SCOPES.map(s => {
          const selected = s.id === activeId
          return (
            <button
              key={s.id}
              role="tab"
              aria-selected={selected}
              className={`scope-tab ${selected ? 'is-active' : ''} ${s.isLive ? 'is-live' : 'is-sim'}`}
              onClick={() => onSelect(s.id)}
              title={`${s.name} · threshold ${s.thresholdPct.toFixed(2)}% (${s.feeBreakdown})`}
            >
              <span className="scope-tab-top">
                <span className="scope-tab-name">{s.name}</span>
                <span className={`scope-tab-badge ${s.isLive ? 'is-live' : 'is-sim'}`}>
                  {s.isLive ? 'LIVE' : 'SIM'}
                </span>
              </span>
              <span className="scope-tab-threshold">
                threshold {s.thresholdPct.toFixed(2)}%
              </span>
              <span className="scope-tab-tagline">{s.tagline}</span>
            </button>
          )
        })}
      </div>

      <ScopeBreakdown scope={active} />

      <div className="scope-tabs-disclosure">
        <span className="scope-tabs-disclosure-icon">ⓘ</span>
        <span>
          <strong>Live REST feed is Binance only.</strong>{' '}
          The Bybit tab re-filters the same Binance stream against Bybit's retail fee envelope
          (VIP0 + USDC-promo 50%-off-taker), showing what <em>would</em> settle if Bybit's
          REST were wired. Live-migration hook: replace the Binance REST block in{' '}
          <code>producers/dual_quote_agent/main.py</code>.
        </span>
      </div>
    </section>
  )
}

function ScopeBreakdown({ scope }: { scope: ExchangeScope }) {
  return (
    <div className={`scope-breakdown ${scope.isLive ? 'is-live' : 'is-sim'}`}>
      <div className="scope-breakdown-left">
        <div className="scope-breakdown-label">Current scope</div>
        <div className="scope-breakdown-name">
          {scope.name}{' '}
          <span className={`scope-tab-badge ${scope.isLive ? 'is-live' : 'is-sim'}`}>
            {scope.isLive ? 'LIVE REST' : 'SIM (fee envelope)'}
          </span>
        </div>
      </div>
      <div className="scope-breakdown-mid">
        <div className="scope-breakdown-label">Threshold</div>
        <div className="scope-breakdown-threshold">{scope.thresholdPct.toFixed(2)}%</div>
        <div className="scope-breakdown-math">
          = {scope.feePct.toFixed(2)}% fees + {scope.bufferPct.toFixed(2)}% buffer
        </div>
      </div>
      <div className="scope-breakdown-right">
        <div className="scope-breakdown-label">Fee breakdown</div>
        <div className="scope-breakdown-detail">{scope.feeBreakdown}</div>
      </div>
    </div>
  )
}
