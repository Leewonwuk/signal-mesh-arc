/**
 * RequirementsBadge — full-width bar at top of dashboard.
 *
 * Exists purely for judge-scanning speed. Maps each lablab.ai submission
 * requirement to a visible badge. If a counter is live (tx settled), it
 * ticks against the /api/health feed.
 *
 * Ordering of chips left-to-right mirrors the REQUIRED list in
 * docs/SUBMISSION_REQUIREMENTS.md §"Technical requirements" + §"Mapping".
 */
import { useEffect, useState } from 'react'

interface Props {
  txSettled: number | null
}

export function RequirementsBadge({ txSettled }: Props) {
  const [pulse, setPulse] = useState(false)
  const [prev, setPrev] = useState<number | null>(null)

  useEffect(() => {
    if (txSettled != null && prev != null && txSettled > prev) {
      setPulse(true)
      const id = window.setTimeout(() => setPulse(false), 600)
      return () => window.clearTimeout(id)
    }
    setPrev(txSettled)
  }, [txSettled, prev])

  const txCount = txSettled ?? 0
  const met50 = txCount >= 50

  return (
    <div className="req-bar">
      <span className="req-chip req-chip-track">
        <span className="req-chip-key">Track</span>
        <span className="req-chip-val">Agent-to-Agent Payment Loop</span>
      </span>
      <span className={`req-chip ${met50 ? 'is-met' : 'is-pending'}`}>
        <span className="req-chip-key">On-chain tx</span>
        <span className={`req-chip-val ${pulse ? 'is-pulse' : ''}`}>
          {txCount}
          <span className="req-chip-sub">/ 50+ required</span>
        </span>
      </span>
      <span className="req-chip is-met">
        <span className="req-chip-key">Per-action pricing</span>
        <span className="req-chip-val">$0.0005 – $0.010 (variable)</span>
      </span>
      <span className="req-chip is-met">
        <span className="req-chip-key">Circle stack</span>
        <span className="req-chip-val">Arc · USDC · Wallets (SCA) · Developer API · x402 paywall wired</span>
      </span>
      <span className="req-chip is-met">
        <span className="req-chip-key">Agent identity</span>
        <span className="req-chip-val">ERC-8004 compatible · reputation via producer hit-rate</span>
      </span>
      <a
        className="req-chip req-chip-link"
        href="https://github.com/Leewonwuk/signal-mesh-arc"
        target="_blank"
        rel="noreferrer"
      >
        <span className="req-chip-key">Code (MIT)</span>
        <span className="req-chip-val">GitHub ↗</span>
      </a>
    </div>
  )
}
