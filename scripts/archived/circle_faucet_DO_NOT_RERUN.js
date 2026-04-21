#!/usr/bin/env node
// Try Circle faucet drip via API for 4 wallets
const API_KEY = process.env.CIRCLE_API_KEY;
if (!API_KEY) { console.error('need CIRCLE_API_KEY'); process.exit(1); }

const addresses = [
  ['producer_kimchi',     '0x7f190347e5ea8fd40dd24ef5f67f33e813fcf27f'],
  ['producer_dual_quote', '0xc3cd155b38197f1c3d598d0021a945d0f344c3a0'],
  ['meta_agent',          '0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f'],
  ['executor_agent',      '0x4d61a39741d07111aabb6bcb596722bb62d2d819'],
];

const CHAIN = 'ARC-TESTNET';

async function postJson(path, body) {
  const r = await fetch('https://api.circle.com' + path, {
    method: 'POST',
    headers: { Authorization: `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let j; try { j = JSON.parse(text); } catch { j = { raw: text }; }
  return { status: r.status, body: j };
}

(async () => {
  for (const [name, addr] of addresses) {
    console.log(`\n-- ${name}  ${addr}`);
    // try a few known faucet endpoint shapes
    const attempts = [
      ['/v1/faucet/drips', { blockchain: CHAIN, address: addr, native: true, usdc: true }],
      ['/v1/w3s/faucet/drips', { blockchain: CHAIN, address: addr, native: true, usdc: true }],
      ['/v1/faucet/drips', { blockchain: CHAIN, address: addr }],
    ];
    for (const [path, body] of attempts) {
      const r = await postJson(path, body);
      console.log(`   ${path} [${r.status}]`, (r.body.message || JSON.stringify(r.body)).slice(0, 160));
      if (r.status >= 200 && r.status < 300) break;
    }
  }
})().catch((e) => { console.error(e); process.exit(1); });
