/**
 * Exchange fee matrix — static, audited 2026-04-21.
 *
 * All fee values are expressed as decimals (0.001 = 0.10%, not percent).
 *
 * Sources:
 *   - Bybit:    bybit.com/en/help-center/article/Spot-Trading-Fee-Rate
 *               + USDC Perp/Spot 50%-off promo (2026-03 extension)
 *   - Binance:  binance.com/en/fee/trading
 *               + Zero-fee USDC promo announcement 2025-09 (restricted to VIP2-9,
 *                 4 pairs: BNB/ADA/TRX/XRP × USDC; excludes BNB 25% stacking)
 *   - OKX:      okx.com/fees — Lv1..Lv8 spot, OKB discount stacks on taker only
 *   - Coinbase: coinbase.com/advanced-fee-tiers + stablepair carve-out
 *   - MEXC:     mexc.com/fee — 0% maker default; MX token 50% off taker above threshold
 *
 * NOTE on `supportsDualQuoteArb`:
 *   v1.3 strategy requires alt/USDT AND alt/USDC pairs on the same venue so both
 *   quote-currency legs sit on the same orderbook/matching engine. Coinbase
 *   Advanced exposes USDT as an *asset* but only a handful of USD/USDC pairs —
 *   no SOL/USDT, DOGE/USDT, etc. — so the arb is structurally impossible there,
 *   regardless of how cheap the stablepair fees look.
 */

export type FeeRate = number  // decimal, e.g. 0.001 = 10 bp

export interface VipTier {
  /** Stable id, used as React key and persona selection */
  id: string
  /** Display name, e.g. "VIP 0", "Lv 1", "$0-10k" */
  name: string
  /** One-line eligibility description, user-facing */
  volumeGate: string
  maker: FeeRate
  taker: FeeRate
  /** Flag for "retail is almost certainly on this tier" — drives default persona */
  retailDefault?: boolean
}

/**
 * A discount / promotion that can be toggled on top of a base VIP tier.
 * Applied multiplicatively to maker/taker unless the promo is absolute
 * (stablepair carve-outs override rather than discount).
 */
export interface Discount {
  id: string
  label: string
  /** Short subtitle for the toggle UI (shown under the checkbox label) */
  description: string
  /**
   * "multiplier"  — scales (maker, taker) by multiplier / takerMultiplier
   * "pair-override" — replaces (maker, taker) entirely, but only for pairs listed
   *                   in `eligiblePairs`
   */
  type: 'multiplier' | 'pair-override'
  /** Required for type=multiplier: applied to both maker and taker unless takerOnly */
  multiplier?: number
  /** If true, multiplier affects taker only (Bybit USDC promo is taker-only 50%) */
  takerOnly?: boolean
  /** Required for type=pair-override */
  overrideMaker?: FeeRate
  overrideTaker?: FeeRate
  eligiblePairs?: string[]
  /** If set, promo only applies to these VIP tier ids (e.g. Binance USDC promo VIP2+) */
  eligibleVipIds?: string[]
  /** Mutually-exclusive discount ids (e.g. BNB 25% OFF does NOT stack on USDC promo pairs) */
  incompatibleWith?: string[]
  /** If true, user-facing UI should pre-check this toggle for the retail default */
  retailAccessible?: boolean
}

export interface Exchange {
  id: string
  name: string
  /** 0..5 stars for "US retail would recognize this" — used in the compare column */
  usRecognition: 1 | 2 | 3 | 4 | 5
  /** 0..5 stars for "integrates USDC / partners with Circle" */
  circleIntegration: 1 | 2 | 3 | 4 | 5
  /** If false, dual-quote arb can't run here — UI disables the "run simulation" button */
  supportsDualQuoteArb: boolean
  /** Shown as a warning banner when supportsDualQuoteArb=false */
  structuralNote?: string
  vipTiers: VipTier[]
  discounts: Discount[]
  /** One-liner for the tab header (shown below exchange name) */
  tagline: string
}

/** v1.3 symbols — used as the canonical pair list when filtering promos */
export const V13_PAIRS = [
  'BNB/USDC', 'BNB/USDT',
  'ADA/USDC', 'ADA/USDT',
  'TRX/USDC', 'TRX/USDT',
  'XRP/USDC', 'XRP/USDT',
  'DOGE/USDC', 'DOGE/USDT',
  'SOL/USDC', 'SOL/USDT',
  'APT/USDC', 'APT/USDT',
  'FET/USDC', 'FET/USDT',
  'WLD/USDC', 'WLD/USDT',
] as const

export const EXCHANGE_FEE_MATRIX: Record<string, Exchange> = {
  bybit: {
    id: 'bybit',
    name: 'Bybit',
    tagline: 'Retail-accessible USDC promo · Circle partner · #2 global',
    usRecognition: 4,
    circleIntegration: 4,
    supportsDualQuoteArb: true,
    vipTiers: [
      { id: 'vip0', name: 'VIP 0', volumeGate: '30d volume < $1M', maker: 0.001, taker: 0.001, retailDefault: true },
      { id: 'vip1', name: 'VIP 1', volumeGate: '30d volume ≥ $1M', maker: 0.0006, taker: 0.0007 },
      { id: 'vip2', name: 'VIP 2', volumeGate: '30d volume ≥ $5M', maker: 0.0004, taker: 0.0006 },
      { id: 'vip3', name: 'VIP 3', volumeGate: '30d volume ≥ $25M', maker: 0.0002, taker: 0.0005 },
    ],
    discounts: [
      {
        id: 'usdc_taker_50off',
        label: 'USDC taker 50% off promo',
        description: 'Active 2026-03 → present. All VIP tiers. Taker-side only.',
        type: 'multiplier',
        multiplier: 0.5,
        takerOnly: true,
        retailAccessible: true,
      },
    ],
  },

  binance: {
    id: 'binance',
    name: 'Binance',
    tagline: 'Largest by volume · BNB discount · USDC promo gated at VIP 2',
    usRecognition: 5,
    circleIntegration: 4,
    supportsDualQuoteArb: true,
    vipTiers: [
      { id: 'vip0', name: 'VIP 0', volumeGate: '30d volume < $1M', maker: 0.001, taker: 0.001, retailDefault: true },
      { id: 'vip1', name: 'VIP 1', volumeGate: '30d ≥ $1M & ≥ 25 BNB', maker: 0.0009, taker: 0.001 },
      { id: 'vip2', name: 'VIP 2', volumeGate: '30d ≥ $5M & ≥ 100 BNB', maker: 0.0008, taker: 0.001 },
      { id: 'vip3', name: 'VIP 3', volumeGate: '30d ≥ $20M & ≥ 250 BNB', maker: 0.00042, taker: 0.0006 },
    ],
    discounts: [
      {
        id: 'bnb_25off',
        label: 'Pay fees in BNB (25% off)',
        description: 'Stacks on every pair EXCEPT the 4-pair USDC zero-fee promo.',
        type: 'multiplier',
        multiplier: 0.75,
        retailAccessible: true,
        incompatibleWith: ['usdc_zero_fee'],
      },
      {
        id: 'usdc_zero_fee',
        label: 'USDC zero-fee promo (VIP 2+, 4 pairs)',
        description: 'BNB/ADA/TRX/XRP vs USDC only. Maker & taker both free. No VIP volume credit.',
        type: 'pair-override',
        overrideMaker: 0,
        overrideTaker: 0,
        eligiblePairs: ['BNB/USDC', 'ADA/USDC', 'TRX/USDC', 'XRP/USDC'],
        eligibleVipIds: ['vip2', 'vip3'],
        incompatibleWith: ['bnb_25off'],
        retailAccessible: false,
      },
    ],
  },

  okx: {
    id: 'okx',
    name: 'OKX',
    tagline: 'Deep liquidity · OKB stacks on taker · global #3-4',
    usRecognition: 3,
    circleIntegration: 3,
    supportsDualQuoteArb: true,
    vipTiers: [
      { id: 'lv1', name: 'Lv 1', volumeGate: '< $10M or default retail', maker: 0.0008, taker: 0.001, retailDefault: true },
      { id: 'lv2', name: 'Lv 2', volumeGate: '≥ $10M 30d volume', maker: 0.0007, taker: 0.0009 },
      { id: 'lv5', name: 'Lv 5', volumeGate: 'holds 2,000 OKB or high volume', maker: 0.0006, taker: 0.0008 },
    ],
    discounts: [
      {
        id: 'okb_40off',
        label: 'Pay fees in OKB (up to 40% off)',
        description: 'Stacks on taker side; exact rate depends on holdings.',
        type: 'multiplier',
        multiplier: 0.6,
        retailAccessible: true,
      },
    ],
  },

  coinbase: {
    id: 'coinbase',
    name: 'Coinbase Advanced',
    tagline: 'Circle co-founder · NYSE-listed · reference-only (no alt/USDT)',
    usRecognition: 5,
    circleIntegration: 5,
    supportsDualQuoteArb: false,
    structuralNote:
      'Coinbase Advanced has USD/USDC pairs for alts but NO alt/USDT pairs. ' +
      'Dual-quote (USDT vs USDC spread) arb cannot execute here — included as a ' +
      'reference narrative only (Circle credibility / US regulatory fit).',
    vipTiers: [
      { id: 't1', name: '$0-10k', volumeGate: '30d < $10k', maker: 0.004, taker: 0.006, retailDefault: true },
      { id: 't2', name: '$10k-50k', volumeGate: '30d $10k-$50k', maker: 0.0025, taker: 0.004 },
      { id: 't3', name: '$50k-100k', volumeGate: '30d $50k-$100k', maker: 0.002, taker: 0.0025 },
      { id: 't4', name: '$100k-1M', volumeGate: '30d $100k-$1M', maker: 0.001, taker: 0.002 },
    ],
    discounts: [
      {
        id: 'stablepair',
        label: 'Stablepair tier (22 pairs)',
        description: 'USDC/USD, USDT/USD, and 20 other stable-stable pairs: 0%/0.001%.',
        type: 'pair-override',
        overrideMaker: 0,
        overrideTaker: 0.00001,
        eligiblePairs: ['USDC/USD', 'USDT/USD'],
        retailAccessible: true,
      },
    ],
  },

  mexc: {
    id: 'mexc',
    name: 'MEXC',
    tagline: 'Lowest published fees · 0% maker default · US footprint thin',
    usRecognition: 2,
    circleIntegration: 2,
    supportsDualQuoteArb: true,
    vipTiers: [
      { id: 'default', name: 'Default spot', volumeGate: 'All users', maker: 0, taker: 0.0005, retailDefault: true },
    ],
    discounts: [
      {
        id: 'mx_50off',
        label: 'Hold ≥ 500 MX (50% off taker)',
        description: 'MEXC native token discount. Maker already 0%, affects taker only.',
        type: 'multiplier',
        multiplier: 0.5,
        takerOnly: true,
        retailAccessible: true,
      },
    ],
  },
}

/** Ordered list for tab rendering — primary venues first */
export const EXCHANGE_ORDER: readonly string[] = ['bybit', 'binance', 'okx', 'coinbase', 'mexc']
