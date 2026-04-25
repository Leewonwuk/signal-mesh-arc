#!/usr/bin/env node
/**
 * Deploy AlphaLoopAgentRegistry to Arc testnet and register 4 wallets.
 *
 * Steps:
 *   1. Compile contracts/AlphaLoopAgentRegistry.sol with solc 0.8.24
 *   2. Detect Arc chainId via eth_chainId
 *   3. Deploy contract using EXECUTOR_PRIVATE_KEY
 *   4. For each of 4 roles (producer-dual-quote, producer-kimchi, meta-agent,
 *      executor-agent): compute sha256 of the registration-v1 card, call
 *      registerAgent(wallet, role, agentURI, contentHash)
 *   5. Write docs/evidence/erc8004_registry.json with all tx hashes + address
 *
 * Run from project root:
 *   cd bridge && set -a && . ../.env && set +a && node scripts/deploy_agent_registry.js
 */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import solc from 'solc'
import {
  createPublicClient,
  createWalletClient,
  defineChain,
  encodeDeployData,
  http,
  parseAbi,
} from 'viem'
import { privateKeyToAccount } from 'viem/accounts'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..', '..')
const CONTRACT_PATH = path.join(REPO_ROOT, 'contracts', 'AlphaLoopAgentRegistry.sol')
const EVIDENCE_PATH = path.join(REPO_ROOT, 'docs', 'evidence', 'erc8004_registry.json')

const PK = process.env.EXECUTOR_PRIVATE_KEY
if (!PK) {
  console.error('ERR: EXECUTOR_PRIVATE_KEY not set in env')
  process.exit(1)
}
const pkNormalized = PK.startsWith('0x') ? PK : `0x${PK}`

const RPC_URL = process.env.ARC_RPC_URL || 'https://rpc.testnet.arc.network'

const WALLETS = [
  {
    role: 'producer_dual_quote',
    cardBasename: 'producer-dual-quote.json',
    wallet: '0xc3cd155b38197f1c3d598d0021a945d0f344c3a0',
  },
  {
    role: 'producer_kimchi',
    cardBasename: 'producer-kimchi.json',
    wallet: '0x7f190347e5ea8fd40dd24ef5f67f33e813fcf27f',
  },
  {
    role: 'meta_agent',
    cardBasename: 'meta-agent.json',
    wallet: '0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f',
  },
  {
    role: 'executor_agent',
    cardBasename: 'executor-agent.json',
    wallet: '0x4d61a39741d07111aabb6bcb596722bb62d2d819',
  },
]

function compile() {
  console.log('[1/5] compile AlphaLoopAgentRegistry.sol')
  const source = fs.readFileSync(CONTRACT_PATH, 'utf8')
  const input = {
    language: 'Solidity',
    sources: { 'AlphaLoopAgentRegistry.sol': { content: source } },
    settings: {
      optimizer: { enabled: true, runs: 200 },
      outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } },
    },
  }
  const output = JSON.parse(solc.compile(JSON.stringify(input)))
  if (output.errors) {
    const fatal = output.errors.filter(e => e.severity === 'error')
    if (fatal.length) {
      console.error('       solc errors:')
      for (const e of fatal) console.error('       ', e.formattedMessage)
      process.exit(2)
    }
    for (const w of output.errors) console.warn('       ', w.formattedMessage)
  }
  const contract = output.contracts['AlphaLoopAgentRegistry.sol']['AlphaLoopAgentRegistry']
  console.log(`       bytecode: ${contract.evm.bytecode.object.length / 2} bytes`)
  return {
    abi: contract.abi,
    bytecode: `0x${contract.evm.bytecode.object}`,
  }
}

function cardContentHash(cardBasename) {
  const p = path.join(REPO_ROOT, 'bridge', 'agent-cards', cardBasename)
  const raw = fs.readFileSync(p, 'utf8')
  // sha256 → hex → 0x-prefixed 32 bytes
  const digest = crypto.createHash('sha256').update(raw, 'utf8').digest('hex')
  return `0x${digest}`
}

async function main() {
  const { abi, bytecode } = compile()

  console.log(`[2/5] connect RPC ${RPC_URL}`)
  const publicClient = createPublicClient({ transport: http(RPC_URL) })
  const chainId = await publicClient.getChainId()
  console.log(`       chainId = ${chainId}`)

  const arc = defineChain({
    id: chainId,
    name: 'Arc testnet',
    nativeCurrency: { name: 'USDC', symbol: 'USDC', decimals: 18 },
    rpcUrls: { default: { http: [RPC_URL] } },
    blockExplorers: { default: { name: 'Arcscan', url: 'https://testnet.arcscan.app' } },
  })

  const account = privateKeyToAccount(pkNormalized)
  console.log(`       operator   = ${account.address}`)
  const balance = await publicClient.getBalance({ address: account.address })
  console.log(`       balance    = ${balance} wei (${Number(balance) / 1e18} USDC-as-gas)`)
  if (balance === 0n) {
    console.error('ERR: operator has zero Arc native balance; drip from faucet first')
    process.exit(3)
  }

  const walletClient = createWalletClient({ account, chain: arc, transport: http(RPC_URL) })

  console.log('[3/5] deploy contract')
  const deployHash = await walletClient.deployContract({ abi, bytecode, args: [] })
  console.log(`       deploy tx  = ${deployHash}`)
  const deployReceipt = await publicClient.waitForTransactionReceipt({ hash: deployHash })
  const contractAddress = deployReceipt.contractAddress
  console.log(`       deployed   = ${contractAddress}  (block ${deployReceipt.blockNumber})`)

  console.log('[4/5] register 4 agent cards')
  const registrations = []
  for (const w of WALLETS) {
    const agentURI = `https://signal-mesh.vercel.app/.well-known/agent-card/${w.cardBasename.replace('.json', '')}`
    const contentHash = cardContentHash(w.cardBasename)
    console.log(`       ${w.role} -> ${agentURI}`)
    console.log(`           contentHash = ${contentHash}`)
    const txHash = await walletClient.writeContract({
      address: contractAddress,
      abi,
      functionName: 'registerAgent',
      args: [w.wallet, w.role, agentURI, contentHash],
    })
    console.log(`           tx = ${txHash}`)
    const receipt = await publicClient.waitForTransactionReceipt({ hash: txHash })
    registrations.push({
      role: w.role,
      wallet: w.wallet,
      agentURI,
      contentHash,
      txHash,
      blockNumber: Number(receipt.blockNumber),
    })
  }

  console.log('[5/5] write evidence file')
  const evidence = {
    project: 'AlphaLoop',
    spec: 'https://eips.ethereum.org/EIPS/eip-8004#registration-v1',
    generatedAt: new Date().toISOString(),
    chainId,
    rpc: RPC_URL,
    contract: 'AlphaLoopAgentRegistry',
    contractAddress,
    operator: account.address,
    deployTx: deployHash,
    deployBlock: Number(deployReceipt.blockNumber),
    registrations,
    verifyHints: {
      contract: `https://testnet.arcscan.app/address/${contractAddress}`,
      firstRegistration: `https://testnet.arcscan.app/tx/${registrations[0].txHash}`,
      howToVerify:
        'Each agent card JSON is served from https://signal-mesh.vercel.app/.well-known/agent-card/<role>. ' +
        'Recompute sha256 of the JSON and compare to the contentHash logged in AgentRegistered event.',
    },
  }
  fs.mkdirSync(path.dirname(EVIDENCE_PATH), { recursive: true })
  fs.writeFileSync(EVIDENCE_PATH, JSON.stringify(evidence, null, 2) + '\n')
  console.log(`       wrote ${path.relative(REPO_ROOT, EVIDENCE_PATH)}`)
  console.log('')
  console.log('===== ERC-8004 deployment complete =====')
  console.log(`registry: ${contractAddress}`)
  for (const r of registrations) {
    console.log(`  ${r.role.padEnd(22)} tx=${r.txHash}`)
  }
}

main().catch(e => {
  console.error('FATAL:', e.message)
  if (e.stack) console.error(e.stack)
  process.exit(9)
})
