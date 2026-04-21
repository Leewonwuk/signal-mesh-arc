#!/usr/bin/env node
// Pre-flight: validate signing pipeline with 0-balance transfer call.
// Expected: INSUFFICIENT_FUNDS (= auth/ciphertext/wallet/token all good, just no money).
// Any other error tells us what ELSE needs fixing before tomorrow's faucet drip.
//
// Usage (Git Bash):
//   set -a; source .env; set +a
//   node scripts/circle_preflight_transfer.js
//
// Does NOT touch the faucet — zero quota impact.

const crypto = require('crypto');

const API_KEY = process.env.CIRCLE_API_KEY;
const ENTITY_SECRET_HEX = process.env.CIRCLE_ENTITY_SECRET;
if (!API_KEY || !ENTITY_SECRET_HEX) {
  console.error('need CIRCLE_API_KEY and CIRCLE_ENTITY_SECRET in env');
  process.exit(1);
}
if (!/^[0-9a-fA-F]{64}$/.test(ENTITY_SECRET_HEX)) {
  console.error('CIRCLE_ENTITY_SECRET must be 64 hex chars');
  process.exit(1);
}

// producer_kimchi → meta_agent, 0.01 USDC
const SRC_WALLET_ID   = '9bf23153-8d5f-5e7b-912c-dc803e3cfac4'; // producer_kimchi
const DST_ADDRESS     = '0xf8f1ae7b49901e6a93b5ddf7f5bd7af998466a0f'; // meta_agent
const AMOUNT          = '0.01';
const BLOCKCHAIN      = 'ARC-TESTNET';

async function freshCiphertext() {
  const r = await fetch('https://api.circle.com/v1/w3s/config/entity/publicKey', {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  if (!r.ok) throw new Error(`publicKey fetch ${r.status}: ${await r.text()}`);
  const pem = (await r.json())?.data?.publicKey;
  if (!pem) throw new Error('publicKey missing');
  const cipher = crypto.publicEncrypt(
    { key: pem, padding: crypto.constants.RSA_PKCS1_OAEP_PADDING, oaepHash: 'sha256' },
    Buffer.from(ENTITY_SECRET_HEX, 'hex')
  );
  return cipher.toString('base64');
}

function uuid() {
  return crypto.randomUUID();
}

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

function diagnose(res) {
  const status = res.status;
  const msg = (res.body?.message || JSON.stringify(res.body)).toLowerCase();
  if (status === 401 || status === 403) return ['AUTH_FAIL', 'API key rejected — check CIRCLE_API_KEY'];
  if (msg.includes('entity') && msg.includes('secret')) return ['CIPHERTEXT_FAIL', 'entity secret ciphertext problem — check CIRCLE_ENTITY_SECRET matches registered ciphertext'];
  if (msg.includes('wallet') && (msg.includes('not found') || msg.includes('invalid'))) return ['WALLET_FAIL', 'walletId not recognized'];
  if (msg.includes('insufficient') || msg.includes('balance') || msg.includes('funds')) return ['PIPELINE_OK', '✓ auth + ciphertext + wallet + token all accepted — only money missing'];
  if (msg.includes('token') && msg.includes('not found')) return ['TOKEN_LOOKUP_NEEDED', 'tokenId required — need to query token list'];
  if (status >= 200 && status < 300) return ['UNEXPECTED_SUCCESS', 'transfer accepted — if wallet is 0, check what got charged'];
  return ['UNKNOWN', `status=${status}, body=${JSON.stringify(res.body).slice(0,300)}`];
}

(async () => {
  console.log('=== Circle signing pipeline pre-flight ===');
  console.log(`src wallet id: ${SRC_WALLET_ID}`);
  console.log(`dst address:   ${DST_ADDRESS}`);
  console.log(`amount:        ${AMOUNT} USDC (native on ${BLOCKCHAIN})`);
  console.log('');

  console.log('[1/3] generating fresh ciphertext...');
  const ciphertext = await freshCiphertext();
  console.log(`  ciphertext length=${ciphertext.length} b64 chars, first 16='${ciphertext.slice(0,16)}...'`);

  console.log('[2/3] posting /v1/w3s/developer/transactions/transfer (native token route)...');
  const body = {
    idempotencyKey: uuid(),
    walletId: SRC_WALLET_ID,
    destinationAddress: DST_ADDRESS,
    amounts: [AMOUNT],
    blockchain: BLOCKCHAIN,
    feeLevel: 'MEDIUM',
    entitySecretCiphertext: ciphertext,
  };
  const res = await postJson('/v1/w3s/developer/transactions/transfer', body);
  console.log(`  HTTP ${res.status}`);
  console.log('  response:', JSON.stringify(res.body, null, 2).slice(0, 800));

  console.log('');
  console.log('[3/3] diagnosis:');
  const [code, explanation] = diagnose(res);
  console.log(`  ${code} — ${explanation}`);

  // If native route failed with token issue, try tokenId route as a follow-up hint.
  if (code === 'TOKEN_LOOKUP_NEEDED') {
    console.log('');
    console.log('-- follow-up: listing tokens to find USDC tokenId --');
    const tokensRes = await fetch('https://api.circle.com/v1/w3s/tokens?blockchain=' + BLOCKCHAIN, {
      headers: { Authorization: `Bearer ${API_KEY}` },
    });
    const tokensBody = await tokensRes.text();
    console.log(`  GET /v1/w3s/tokens [${tokensRes.status}]: ${tokensBody.slice(0, 400)}`);
  }
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
