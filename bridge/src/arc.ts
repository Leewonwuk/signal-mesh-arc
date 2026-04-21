// Arc Testnet chain config for viem
import { defineChain } from 'viem'

export const arcTestnet = defineChain({
  id: 5042002,
  name: 'Arc Testnet',
  nativeCurrency: { name: 'USDC', symbol: 'USDC', decimals: 18 },
  rpcUrls: {
    default: { http: ['https://rpc.testnet.arc.network'] },
  },
  blockExplorers: {
    default: { name: 'ArcScan', url: 'https://testnet.arcscan.app' },
  },
})

// USDC contract on Arc testnet
// ⚠️ DUAL DECIMAL: native=18, ERC-20=6. Always use 6 for transfer/approve amounts.
export const USDC_ADDRESS = '0x3600000000000000000000000000000000000000' as const

export const USDC_ABI = [
  {
    type: 'function',
    name: 'transfer',
    stateMutability: 'nonpayable',
    inputs: [
      { name: 'to', type: 'address' },
      { name: 'amount', type: 'uint256' },
    ],
    outputs: [{ type: 'bool' }],
  },
  {
    type: 'function',
    name: 'balanceOf',
    stateMutability: 'view',
    inputs: [{ name: 'account', type: 'address' }],
    outputs: [{ type: 'uint256' }],
  },
] as const

// Convert human-readable USDC amount to ERC-20 base units (6 decimals).
export const toUsdcBaseUnits = (amount: number): bigint =>
  BigInt(Math.round(amount * 1_000_000))
