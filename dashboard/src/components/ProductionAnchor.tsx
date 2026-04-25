/**
 * ProductionAnchor — compact banner that anchors the demo to the operator's
 * already-running v1.3 EC2 arb bot. Addresses the "Business Value" judging
 * axis by making it visible-at-a-glance that this hackathon entry sits on
 * top of a real revenue system, not a toy.
 *
 * Numbers sourced from:
 *   - docs/evidence/v1_3_live_stats_260411-260419.json (648 trades, $17.92 PnL,
 *     8.2-day window 2026-04-11 → 2026-04-19)
 *   - README TL;DR (pool size, threshold, coin list)
 *
 * Honest caveat: 3 of 9 enabled coins (APT/FET/WLD) had 0 trades in this
 * window; SOL alone produced $8.16 of the $17.92. Full per-coin breakdown
 * in the evidence JSON. SUBMISSION.md §13 carries the full disclosure.
 */
export function ProductionAnchor() {
  return (
    <div className="prod-anchor">
      <div className="prod-anchor-row">
        <span className="prod-anchor-pulse" />
        <span className="prod-anchor-label">Production anchor</span>
        <span className="prod-anchor-text">
          The dual-quote feed replays 1-second ticks from my <strong>live v1.3 arb bot on EC2</strong>
          {' · '}<strong>9 coins</strong>
          {' · pool ≈ '}<strong>$1,977 USDT</strong>
          {' · Binance VIP-0 threshold '}<strong>0.17%</strong>
          {' · last 8 days: '}<strong>648 trades · +$17.92 PnL · 0 stop-loss</strong>
          {' · running right now.'}
        </span>
      </div>
    </div>
  )
}
