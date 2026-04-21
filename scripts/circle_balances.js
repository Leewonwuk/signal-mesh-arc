#!/usr/bin/env node
// Check USDC balances for all 4 wallets
const API_KEY = process.env.CIRCLE_API_KEY;
if (!API_KEY) { console.error('need CIRCLE_API_KEY'); process.exit(1); }

const wallets = [
  ['producer_kimchi',     '9bf23153-8d5f-5e7b-912c-dc803e3cfac4', '0x7f190347e5ea8fd40dd24ef5f67f33e813fcf27f'],
  ['producer_dual_quote', 'f3f656e3-9b9c-5f7f-85eb-3a94b94b22aa', '0xc3cd155b38197f1c3d598d0021a945d0f344c3a0'],
  ['meta_agent',          'bdd21d61-4186-5861-8851-e8300b137faa', '0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f'],
  ['executor_agent',      '18b55b76-3a5a-576d-8cd6-043563093957', '0x4d61a39741d07111aabb6bcb596722bb62d2d819'],
];

async function getBalance(id) {
  const r = await fetch(`https://api.circle.com/v1/w3s/wallets/${id}/balances`, {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  return { status: r.status, body: await r.json() };
}

(async () => {
  let total = 0;
  for (const [name, id, addr] of wallets) {
    const r = await getBalance(id);
    const tokens = r.body?.data?.tokenBalances || [];
    const usdc = tokens.find(t => (t.token?.symbol || '').toUpperCase() === 'USDC');
    const amount = usdc ? parseFloat(usdc.amount) : 0;
    total += amount;
    const marker = amount > 0 ? '✅' : '❌';
    console.log(`${marker} ${name.padEnd(22)} ${amount.toFixed(4).padStart(12)} USDC   ${addr}`);
    if (tokens.length > 0 && !usdc) {
      console.log('     (other tokens:', tokens.map(t => `${t.token?.symbol}=${t.amount}`).join(', '), ')');
    }
  }
  console.log('---');
  console.log('TOTAL:', total.toFixed(4), 'USDC');
})();
