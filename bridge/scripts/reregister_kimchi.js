#!/usr/bin/env node
/**
 * Re-register producer_kimchi on AlphaLoopAgentRegistry after the initial
 * tx reverted with out-of-gas. viem's gas estimation undershot on that
 * specific call; we force 350k gas here.
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
const CARD_PATH = path.join(REPO_ROOT, 'bridge', 'agent-cards', 'producer-kimchi.json')

const PK = process.env.EXECUTOR_PRIVATE_KEY
if (!PK) {
  console.error('ERR: EXECUTOR_PRIVATE_KEY not set')
  process.exit(1)
}

const pkNormalized = PK.startsWith('0x') ? PK : `0x${PK}`
const RPC_URL = process.env.ARC_RPC_URL || 'https://rpc.testnet.arc.network'
const REGISTRY = '0xb276b96f2da05c46b60d4b38e9beaf7d3355b7ab'
const KIMCHI_WALLET = '0x7f190347e5ea8fd40dd24ef5f67f33e813fcf27f'
const KIMCHI_URI = 'https://signal-mesh.vercel.app/.well-known/agent-card/producer-kimchi'

const ABI = parseAbi([
  'function registerAgent(address wallet, string calldata role, string calldata agentURI, bytes32 contentHash) external returns (uint256)',
  'event AgentRegistered(uint256 indexed agentId, address indexed wallet, string role, string agentURI, bytes32 contentHash)',
])

async function main() {
  const raw = fs.readFileSync(CARD_PATH, 'utf8')
  const contentHash = `0x${crypto.createHash('sha256').update(raw, 'utf8').digest('hex')}`
  console.log(`kimchi card sha256: ${contentHash}`)

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

  console.log(`Re-registering producer_kimchi (forcing gas=350000)`)
  const txHash = await walletClient.writeContract({
    address: REGISTRY,
    abi: ABI,
    functionName: 'registerAgent',
    args: [KIMCHI_WALLET, 'producer_kimchi', KIMCHI_URI, contentHash],
    gas: 350000n,
  })
  console.log(`tx = ${txHash}`)
  const receipt = await publicClient.waitForTransactionReceipt({ hash: txHash })
  console.log(`status = ${receipt.status}, block = ${receipt.blockNumber}, gasUsed = ${receipt.gasUsed}`)
  if (receipt.status !== 'success') {
    console.error('STILL REVERTED. Giving up.')
    process.exit(2)
  }

  // Patch evidence file
  const evidence = JSON.parse(fs.readFileSync(EVIDENCE_PATH, 'utf8'))
  const reg = evidence.registrations.find(r => r.role === 'producer_kimchi')
  if (!reg) {
    console.error('ERR: kimchi entry not found in registry JSON')
    process.exit(3)
  }
  reg.originalFailedTx = reg.txHash
  reg.txHash = txHash
  reg.contentHash = contentHash
  reg.blockNumber = Number(receipt.blockNumber)
  reg.gasUsed = Number(receipt.gasUsed)
  reg.rerunAt = new Date().toISOString()
  evidence.reruns = evidence.reruns || []
  evidence.reruns.push({
    role: 'producer_kimchi',
    reason: 'initial tx reverted with out-of-gas (gas_used=28877)',
    newTx: txHash,
    at: new Date().toISOString(),
  })
  fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n')
  console.log(`Patched ${path.relative(REPO_ROOT, EVIDENCE_PATH)}`)
  console.log('===== kimchi re-registered =====')
  console.log(`  new tx: ${txHash}`)
  console.log(`  block : ${receipt.blockNumber}`)
}

main().catch(e => {
  console.error('FATAL:', e.message)
  if (e.stack) console.error(e.stack)
  process.exit(9)
})
