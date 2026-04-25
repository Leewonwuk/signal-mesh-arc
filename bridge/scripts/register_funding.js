#!/usr/bin/env node
/**
 * Register producer_funding (v3 lane) on AlphaLoopAgentRegistry.
 *
 * v3 was introduced after the original 4-agent batch, so it gets its own
 * registration script (mirrors reregister_kimchi.js style — force gas=350k
 * because viem's estimator undershot on the analogous kimchi call).
 *
 * Run from project root:
 *   set -a && . .env && set +a && node bridge/scripts/register_funding.js
 *
 * On success, patches docs/evidence/erc8004_registry.json with the new
 * registration row so the dashboard's AgentIdentityCard picks it up.
 */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import {
  createPublicClient,
  createWalletClient,
  defineChain,
  http,
  parseAbi,
} from 'viem'
import { privateKeyToAccount } from 'viem/accounts'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..')
const EVIDENCE_PATH = path.join(REPO_ROOT, 'docs', 'evidence', 'erc8004_registry.json')
const CARD_PATH = path.join(REPO_ROOT, 'bridge', 'agent-cards', 'producer-funding.json')

const PK = process.env.EXECUTOR_PRIVATE_KEY
if (!PK) {
  console.error('ERR: EXECUTOR_PRIVATE_KEY not set')
  process.exit(1)
}

const pkNormalized = PK.startsWith('0x') ? PK : `0x${PK}`
const RPC_URL = process.env.ARC_RPC_URL || 'https://rpc.testnet.arc.network'
const REGISTRY = '0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab'
const FUNDING_WALLET = '0xf90a57d3410ad342a3b85d22f6e7009db88565df'
const FUNDING_URI = 'https://signal-mesh.vercel.app/.well-known/agent-card/producer-funding'

const ABI = parseAbi([
  'function registerAgent(address wallet, string calldata role, string calldata agentURI, bytes32 contentHash) external returns (uint256)',
  'event AgentRegistered(uint256 indexed agentId, address indexed wallet, string role, string agentURI, bytes32 contentHash)',
])

async function main() {
  const raw = fs.readFileSync(CARD_PATH, 'utf8')
  const contentHash = `0x${crypto.createHash('sha256').update(raw, 'utf8').digest('hex')}`
  console.log(`funding card sha256: ${contentHash}`)

  const publicClient = createPublicClient({ transport: http(RPC_URL) })
  const chainId = await publicClient.getChainId()
  const arc = defineChain({
    id: chainId,
    name: 'Arc testnet',
    nativeCurrency: { name: 'USDC', symbol: 'USDC', decimals: 18 },
    rpcUrls: { default: { http: [RPC_URL] } },
  })

  const account = privateKeyToAccount(pkNormalized)
  const walletClient = createWalletClient({ account, chain: arc, transport: http(RPC_URL) })

  console.log(`Registering producer_funding (forcing gas=350000)`)
  const txHash = await walletClient.writeContract({
    address: REGISTRY,
    abi: ABI,
    functionName: 'registerAgent',
    args: [FUNDING_WALLET, 'producer_funding', FUNDING_URI, contentHash],
    gas: 350000n,
  })
  console.log(`tx = ${txHash}`)
  const receipt = await publicClient.waitForTransactionReceipt({ hash: txHash })
  console.log(`status = ${receipt.status}, block = ${receipt.blockNumber}, gasUsed = ${receipt.gasUsed}`)
  if (receipt.status !== 'success') {
    console.error('REVERTED. Aborting evidence patch.')
    process.exit(2)
  }

  // Patch evidence file
  const evidence = JSON.parse(fs.readFileSync(EVIDENCE_PATH, 'utf8'))
  const existing = evidence.registrations.find(r => r.role === 'producer_funding')
  if (existing) {
    console.log('Already registered — patching tx hash to latest run')
    existing.txHash = txHash
    existing.contentHash = contentHash
    existing.blockNumber = Number(receipt.blockNumber)
    existing.gasUsed = Number(receipt.gasUsed)
    existing.rerunAt = new Date().toISOString()
  } else {
    evidence.registrations.push({
      role: 'producer_funding',
      wallet: FUNDING_WALLET,
      agentURI: FUNDING_URI,
      contentHash,
      txHash,
      blockNumber: Number(receipt.blockNumber),
      gasUsed: Number(receipt.gasUsed),
      registeredAt: new Date().toISOString(),
    })
  }
  fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n')
  console.log(`Patched ${path.relative(REPO_ROOT, EVIDENCE_PATH)}`)
  console.log('===== producer_funding registered =====')
  console.log(`  tx   : ${txHash}`)
  console.log(`  block: ${receipt.blockNumber}`)
  console.log(`  hash : ${contentHash}`)
}

main().catch(e => {
  console.error('FATAL:', e.message)
  if (e.stack) console.error(e.stack)
  process.exit(9)
})
