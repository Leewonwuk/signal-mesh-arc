/**
 * WhyArcCard — the margin-explanation visual the hackathon requires
 * (SUBMISSION_REQUIREMENTS §"why traditional gas would kill this model").
 *
 * Two-column delta: other-L1 (ETH gas) vs Arc (USDC gas). Numbers match the
 * video narration at 0:05-0:30 and SUBMISSION.md §4.
 *
 * 2026-04-25 honesty patch (Option B — snapshot, not live):
 *   Prior version showed "-$0.012 ETH" next to a "-$0.002 MARGIN" which mixed
 *   units. An honest margin requires USDC-equivalent conversion. We do it once
 *   at build time with a dated reference price so judges can audit, rather
 *   than pulling a flaky live feed mid-demo. Upgrade to live fetch later.
 *
 *   Arc gas is the *measured* value from circle_preflight_transfer.js receipt
 *   (tx 0x18e1…b748, block 38806608): 0.00367926 USDC network fee rounded up
 *   to $0.004 for display.
 */

// ── Reference snapshot — update on rebuild ─────────────────────────
const REF = {
  date: '2026-04-25',
  // ETH/USD spot — update this + REF.date before each build.
  ethPriceUsd: 3400,
  // Typical ERC-20 / EIP-3009 transferWithAuthorization gas envelope.
  ethGasUnits: 50_000,
  ethGasPriceGwei: 15,
  // Arc: measured from receipt 0x18e140940559016c3cb4cdfd82446b2c12bb6d51330f0237b9a3c4ec182b7484
  arcGasUsdc: 0.004,
  // Worked-example signal fee (cap of the $0.0005–$0.010 variable range)
  signalFeeUsdc: 0.010,
} as const

const ETH_GAS_ETH = REF.ethGasUnits * REF.ethGasPriceGwei * 1e-9
const ETH_GAS_USD = ETH_GAS_ETH * REF.ethPriceUsd
const ETH_MARGIN_USD = REF.signalFeeUsdc - ETH_GAS_USD
const ARC_MARGIN_USD = REF.signalFeeUsdc - REF.arcGasUsdc

function fmtUsd(v: number, digits = 3): string {
  const sign = v < 0 ? '−' : '+'
  return `${sign}$${Math.abs(v).toFixed(digits)}`
}

export function WhyArcCard() {
  return (
    <section className="why-arc">
      <div className="why-arc-heading">
        <span className="why-arc-eyebrow">Margin reality — why this doesn't work elsewhere</span>
        <span className="why-arc-pricing-note">
          worked example at the $0.010 cap — actual per-action pricing varies $0.0005 – $0.010
        </span>
      </div>
      <div className="why-arc-grid">
        <div className="why-arc-col why-arc-col-bad">
          <div className="why-arc-col-label">Other L1 (ETH / SOL / MATIC gas)</div>
          <div className="why-arc-row">
            <span className="why-arc-row-label">Signal fee earned</span>
            <span className="why-arc-row-num">+$0.010 USDC</span>
          </div>
          <div className="why-arc-row">
            <span className="why-arc-row-label">
              Gas paid (native token)
              <span className="why-arc-row-sublabel">
                {REF.ethGasUnits.toLocaleString()} gas × {REF.ethGasPriceGwei} gwei (median envelope · range 10–50)
              </span>
            </span>
            <span className="why-arc-row-num why-arc-row-neg">
              {fmtUsd(-ETH_GAS_USD, 2)} USDC
              <span className="why-arc-row-sublabel">
                = {ETH_GAS_ETH.toFixed(5)} ETH × ${REF.ethPriceUsd.toLocaleString()} · ref {REF.date}
              </span>
            </span>
          </div>
          <div className="why-arc-row why-arc-row-total">
            <span className="why-arc-row-label">Margin</span>
            <span className="why-arc-row-num why-arc-row-neg">{fmtUsd(ETH_MARGIN_USD, 2)} USDC</span>
          </div>
          <div className="why-arc-col-caption">
            Two-unit accounting · human refills ETH · loop economically dead on arrival.
          </div>
        </div>
        <div className="why-arc-col why-arc-col-good">
          <div className="why-arc-col-label">Arc L1 (USDC is the gas)</div>
          <div className="why-arc-row">
            <span className="why-arc-row-label">Signal fee earned</span>
            <span className="why-arc-row-num">+$0.010 USDC</span>
          </div>
          <div className="why-arc-row">
            <span className="why-arc-row-label">
              Gas paid
              <span className="why-arc-row-sublabel">
                measured · tx 0x18e1…b748
              </span>
            </span>
            <span className="why-arc-row-num why-arc-row-neg">
              {fmtUsd(-REF.arcGasUsdc, 3)} USDC
              <span className="why-arc-row-sublabel">actual 0.00368 · rounded ↑</span>
            </span>
          </div>
          <div className="why-arc-row why-arc-row-total">
            <span className="why-arc-row-label">Margin</span>
            <span className="why-arc-row-num why-arc-row-pos">{fmtUsd(ARC_MARGIN_USD, 3)} USDC</span>
          </div>
          <div className="why-arc-col-caption">
            Same unit in and out · loop closes autonomously · no human refill.
          </div>
        </div>
      </div>
      <div className="why-arc-footer">
        <span>
          ref-price snapshot <strong>{REF.date}</strong> · ETH=${REF.ethPriceUsd.toLocaleString()} ·
          gas envelope is median ERC-20 transfer at {REF.ethGasPriceGwei} gwei · refresh on rebuild.
        </span>
      </div>
    </section>
  )
}
