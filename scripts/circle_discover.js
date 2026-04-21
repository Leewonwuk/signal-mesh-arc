#!/usr/bin/env node
const API_KEY = process.env.CIRCLE_API_KEY;
if (!API_KEY) { console.error('need CIRCLE_API_KEY'); process.exit(1); }

const endpoints = [
  '/v1/w3s/config/entity',
  '/v1/w3s/walletSets',
  '/v1/w3s/wallets',
  '/v1/w3s/blockchains',
  '/v1/w3s/developer/walletSets?pageSize=20',
  '/v1/w3s/developer/wallets?pageSize=20',
  '/v1/w3s/config/chains',
];

async function get(path) {
  const res = await fetch('https://api.circle.com' + path, {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  const text = await res.text();
  console.log(`\n=== GET ${path}  [${res.status}] ===`);
  try { console.log(JSON.stringify(JSON.parse(text), null, 2).slice(0, 2000)); }
  catch { console.log(text.slice(0, 500)); }
}

(async () => {
  for (const p of endpoints) await get(p);
})();
