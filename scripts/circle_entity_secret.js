#!/usr/bin/env node
// Circle Entity Secret ciphertext generator
// Usage:
//   CIRCLE_API_KEY=TEST_API_KEY:... node circle_entity_secret.js
//   CIRCLE_API_KEY=... ENTITY_SECRET_HEX=<64-hex> node circle_entity_secret.js

const crypto = require('crypto');

const API_KEY = process.env.CIRCLE_API_KEY;
if (!API_KEY) {
  console.error('ERROR: set CIRCLE_API_KEY env var');
  process.exit(1);
}

let entitySecretHex = process.env.ENTITY_SECRET_HEX;
if (!entitySecretHex) {
  entitySecretHex = crypto.randomBytes(32).toString('hex');
  console.log('[generated new entity secret]');
}
if (!/^[0-9a-fA-F]{64}$/.test(entitySecretHex)) {
  console.error('ERROR: ENTITY_SECRET_HEX must be 64 hex chars (32 bytes)');
  process.exit(1);
}

async function main() {
  const res = await fetch('https://api.circle.com/v1/w3s/config/entity/publicKey', {
    headers: { Authorization: `Bearer ${API_KEY}` },
  });
  if (!res.ok) {
    console.error(`Circle API error ${res.status}: ${await res.text()}`);
    process.exit(1);
  }
  const body = await res.json();
  const publicKeyPem = body?.data?.publicKey;
  if (!publicKeyPem) {
    console.error('ERROR: publicKey missing from response', body);
    process.exit(1);
  }

  const entitySecretBytes = Buffer.from(entitySecretHex, 'hex');
  const ciphertext = crypto.publicEncrypt(
    {
      key: publicKeyPem,
      padding: crypto.constants.RSA_PKCS1_OAEP_PADDING,
      oaepHash: 'sha256',
    },
    entitySecretBytes
  );

  console.log('\n============================================================');
  console.log('ENTITY_SECRET (raw hex)  ->  put in .env as CIRCLE_ENTITY_SECRET');
  console.log('============================================================');
  console.log(entitySecretHex);
  console.log('\n============================================================');
  console.log('CIPHERTEXT (base64)      ->  paste into Circle Configurator');
  console.log('============================================================');
  console.log(ciphertext.toString('base64'));
  console.log('');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
