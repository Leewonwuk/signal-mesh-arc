#!/usr/bin/env node
// Create Wallet Set + 4 dev-controlled wallets on Arc testnet
// Env: CIRCLE_API_KEY, CIRCLE_ENTITY_SECRET (64 hex)

const crypto = require('crypto');

const API_KEY = process.env.CIRCLE_API_KEY;
const ENTITY_SECRET_HEX = process.env.CIRCLE_ENTITY_SECRET;
if (!API_KEY || !ENTITY_SECRET_HEX) {
  console.error('need CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET'); process.exit(1);
}
const ENTITY_SECRET = Buffer.from(ENTITY_SECRET_HEX, 'hex');
const WALLET_NAMES = ['producer_kimchi', 'producer_dual_quote', 'meta_agent', 'executor_agent'];
const CHAIN_CANDIDATES = (process.env.CIRCLE_CHAIN ? [process.env.CIRCLE_CHAIN] : [
  'ARC-SEPOLIA', 'ARC-TESTNET', 'ARC', 'CIRCLE-ARC-SEPOLIA', 'CIRCLE-ARC-TESTNET',
]);

let cachedPublicKey = null;
async function getPublicKey() {
  if (cachedPublicKey) return cachedPublicKey;
  const r = await fetch('https://api.circle.com/v1/w3s/config/entity/publicKey', {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  const j = await r.json();
  cachedPublicKey = j.data.publicKey;
  return cachedPublicKey;
}

async function freshCiphertext() {
  const pk = await getPublicKey();
  const enc = crypto.publicEncrypt(
    { key: pk, padding: crypto.constants.RSA_PKCS1_OAEP_PADDING, oaepHash: 'sha256' },
    ENTITY_SECRET,
  );
  return enc.toString('base64');
}

async function postJson(path, body) {
  const r = await fetch('https://api.circle.com' + path, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let parsed;
  try { parsed = JSON.parse(text); } catch { parsed = { raw: text }; }
  return { status: r.status, body: parsed };
}

async function createWalletSet(name) {
  return postJson('/v1/w3s/developer/walletSets', {
    idempotencyKey: crypto.randomUUID(),
    entitySecretCiphertext: await freshCiphertext(),
    name,
  });
}

async function createWallets(walletSetId, chain) {
  return postJson('/v1/w3s/developer/wallets', {
    idempotencyKey: crypto.randomUUID(),
    entitySecretCiphertext: await freshCiphertext(),
    blockchains: [chain],
    count: WALLET_NAMES.length,
    walletSetId,
    accountType: 'SCA',
    metadata: WALLET_NAMES.map((name) => ({ name })),
  });
}

(async () => {
  console.log('[1/3] creating wallet set "signal-mesh"...');
  const ws = await createWalletSet('signal-mesh');
  if (ws.status !== 201 && ws.status !== 200) {
    console.error('wallet set failed:', ws.status, JSON.stringify(ws.body, null, 2));
    process.exit(1);
  }
  const walletSetId = ws.body.data.walletSet.id;
  console.log('    walletSetId =', walletSetId);

  console.log('[2/3] trying chain identifiers for Arc testnet...');
  let successChain = null;
  let walletsResp = null;
  for (const chain of CHAIN_CANDIDATES) {
    console.log('    -> try', chain);
    const resp = await createWallets(walletSetId, chain);
    if (resp.status === 201 || resp.status === 200) {
      successChain = chain;
      walletsResp = resp;
      console.log('       SUCCESS with', chain);
      break;
    }
    console.log('       fail [' + resp.status + ']:', resp.body.message || JSON.stringify(resp.body).slice(0,200));
  }
  if (!walletsResp) {
    console.error('\nall chain identifiers failed. Visit Circle docs to find the right one,');
    console.error('then rerun with CIRCLE_CHAIN=<identifier>.');
    console.error('Wallet set "signal-mesh" already exists:', walletSetId);
    process.exit(1);
  }

  console.log('[3/3] parsing wallet results...');
  const wallets = walletsResp.body.data.wallets;
  console.log('\n================ RESULT ================');
  console.log('Wallet Set ID:', walletSetId);
  console.log('Chain:', successChain);
  console.log('----------------------------------------');
  for (const w of wallets) {
    console.log(`  ${w.name?.padEnd(22) || '(unnamed)'.padEnd(22)} ${w.address}   (${w.id})`);
  }
  console.log('========================================');
  console.log('\nJSON dump:');
  console.log(JSON.stringify({ walletSetId, chain: successChain, wallets }, null, 2));
})().catch((e) => { console.error(e); process.exit(1); });
