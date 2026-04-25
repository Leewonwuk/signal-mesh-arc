/**
 * AgentIdentityCard — surfaces AlphaLoop's on-chain ERC-8004 registry
 * (deployed at 0xb276b96f… on Arc testnet) directly in the dashboard fold,
 * so a judge doesn't have to open a separate scoreboard page to see the
 * identity artifact. Data is static (derived from
 * docs/evidence/erc8004_registry.json) — the contract itself is the
 * dynamic source of truth on-chain.
 *
 * Why this is its own component (not a link): AlphaLoop differentiates
 * from Track 2 competitors who claim "ERC-8004 compatible" in README
 * but emit no events. Making the tx hashes + contentHashes visible on
 * the primary dashboard makes the claim auditable in 5 seconds.
 */

interface AgentRow {
  role: string
  roleKey: string
  wallet: string
  cardUrl: string
  contentHash: string
  registerTx: string
  /** When true, the row is rendered as "registration pending" — card is
   *  served and content-addressed but the on-chain AgentRegistered event
   *  has not been emitted yet. Used during the v3 funding rollout window. */
  pending?: boolean
}

const REGISTRY_CONTRACT = '0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab'
const DEPLOY_TX = '0xe71d60b2b6751b230194f0961ef9a5e3cc13aecf41dc23593e542fd62bbd440e'
const CHAIN_NAME = 'Arc testnet'
const CHAIN_ID = 5042002

const AGENTS: AgentRow[] = [
  {
    role: 'Producer · Dual-Quote (live v1.3 replay)',
    roleKey: 'producer-dual-quote',
    wallet: '0xc3cd155b38197f1c3d598d0021a945d0f344c3a0',
    cardUrl: '/.well-known/agent-card/producer-dual-quote.json',
    contentHash: '0x91846a126a7aad94ba7ed77ec066aa491aca75763e2d6ea9036aa042380efd9e',
    registerTx: '0xa9c56517c8da5b14c05264c45f3b37fc12efd2d182a79550ea22c9e560953a93',
  },
  {
    role: 'Producer · Kimchi (synthetic)',
    roleKey: 'producer-kimchi',
    wallet: '0x7f190347e5ea8fd40dd24ef5f67f33e813fcf27f',
    cardUrl: '/.well-known/agent-card/producer-kimchi.json',
    contentHash: '0xbf8dfc36f7c6cb8c25a103149a295132517b925eb066d11400707228640907ff',
    registerTx: '0xc8e39c5e22be9f34f3980ffd8a682d34b807d48d6bc2b09cc22e16850193c2ff',
  },
  {
    role: 'Producer · Funding (v3 · Binance fapi)',
    roleKey: 'producer-funding',
    wallet: '0xf90a57d3410ad342a3b85d22f6e7009db88565df',
    cardUrl: '/.well-known/agent-card/producer-funding.json',
    contentHash: '0x84744682cc59bcbd7722ab96af4979f3960bce30077754afd44ea275d3bab244',
    registerTx: '0xc331169ba725b344bdb8ccfdde9d07773433941e5ee6806ade3db86a214a8f06',
  },
  {
    role: 'Meta · Gemini 2.5 Flash + stub',
    roleKey: 'meta-agent',
    wallet: '0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f',
    cardUrl: '/.well-known/agent-card/meta-agent.json',
    contentHash: '0xf89a9fcb5232cb69c1c284ecddc7ee45e790680167a9c761e8edc1196bdea219',
    registerTx: '0x9c8d6a32986b0c3236b86aae5b6bd944490cabd6eb72d9cdf4d2df85b03d7101',
  },
  {
    role: 'Executor · variable-price x402 settler',
    roleKey: 'executor-agent',
    wallet: '0x4d61a39741d07111aabb6bcb596722bb62d2d819',
    cardUrl: '/.well-known/agent-card/executor-agent.json',
    contentHash: '0x6d23188e2296357fb078f5ec59914758e2a4b0920db824eb0829f160debacacf',
    registerTx: '0x70ac0649289cf435405fb0d2378189f48e24dd417730992001620c5b9bbd26ab',
  },
]

function shortHex(hex: string, head = 6, tail = 4): string {
  if (!hex) return ''
  if (hex.length <= head + tail + 2) return hex
  return `${hex.slice(0, head + 2)}…${hex.slice(-tail)}`
}

export function AgentIdentityCard() {
  return (
    <section className="agent-identity card">
      <div className="agent-identity-header">
        <h2>Agent identity — on-chain ERC-8004</h2>
        <span className="meta">
          AlphaLoopAgentRegistry contract on {CHAIN_NAME} (chainId {CHAIN_ID}) emitted
          {' '}{AGENTS.filter(a => !a.pending).length} <code>AgentRegistered</code> events
          {AGENTS.some(a => a.pending) && (
            <> ({AGENTS.filter(a => a.pending).length} pending — card served, on-chain registration in-flight)</>
          )}. Each event carries the sha256 content hash of the registration-v1 card
          served below — content-addressed off-chain → on-chain linkage judges can verify
          in seconds.
        </span>
      </div>

      <div className="agent-identity-registry">
        <div>
          <div className="agent-identity-label">
            Registry contract · <span className="agent-identity-verified-tag">source verified</span>
          </div>
          <a
            className="agent-identity-contract"
            href={`https://testnet.arcscan.app/address/${REGISTRY_CONTRACT}`}
            target="_blank"
            rel="noreferrer"
          >
            {REGISTRY_CONTRACT}
          </a>
        </div>
        <div>
          <div className="agent-identity-label">Deploy tx</div>
          <a
            className="agent-identity-txlink"
            href={`https://testnet.arcscan.app/tx/${DEPLOY_TX}`}
            target="_blank"
            rel="noreferrer"
          >
            {shortHex(DEPLOY_TX, 10, 6)} ↗
          </a>
        </div>
      </div>

      <div className="agent-identity-scroll">
        <table className="agent-identity-table">
          <thead>
            <tr>
              <th>Role</th>
              <th>Wallet</th>
              <th>Card (sha256 = event contentHash)</th>
              <th>AgentRegistered tx</th>
            </tr>
          </thead>
          <tbody>
            {AGENTS.map(a => (
              <tr key={a.roleKey} className={a.pending ? 'agent-identity-row-pending' : undefined}>
                <td className="agent-identity-role">
                  {a.role}
                  {a.pending && <span className="agent-identity-pending-tag">pending</span>}
                </td>
                <td><code>{shortHex(a.wallet)}</code></td>
                <td>
                  <a className="agent-identity-cardlink" href={a.cardUrl} target="_blank" rel="noreferrer">card ↗</a>
                  <span className="agent-identity-hash">{shortHex(a.contentHash, 10, 6)}</span>
                </td>
                <td>
                  {a.pending ? (
                    <span className="agent-identity-pending-msg">on-chain register in-flight · hash auditable now</span>
                  ) : (
                    <a
                      className="agent-identity-txlink"
                      href={`https://testnet.arcscan.app/tx/${a.registerTx}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {shortHex(a.registerTx, 10, 6)} ↗
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="agent-identity-footer">
        Verify: fetch the card JSON → recompute <code>sha256</code> → compare to the
        <code>contentHash</code> field in the corresponding <code>AgentRegistered</code>
        event. Tamper with a card and the hash no longer matches.
      </div>
      <div className="agent-identity-risk-disclosure">
        <strong>Risk model · honest disclosure:</strong> per-trade notional bounded by{' '}
        <code>min($500 paper × 1/4 Kelly, 0.01% × 24h venue volume)</code>. Threshold
        assumes Bybit VIP-0 promo (config-only revertable). Stop-loss 0.25%, IOC timeout 6s,
        per-coin notional cap as kill-switches. Portfolio-level coordinated halt + ATR-conditioned
        thresholds + VaR/CVaR are <em>v1.32 roadmap</em>. Full text in{' '}
        <code>SUBMISSION.md §13</code>.
      </div>
    </section>
  )
}
