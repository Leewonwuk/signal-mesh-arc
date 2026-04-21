# Circle Product Feedback — Signal Mesh on Arc

> Submission for the **$500 USDC Product Feedback bonus**. Five honest pain
> points encountered while building an agent-to-agent nanopayment marketplace
> on Arc testnet, 2026-04-20 to 2026-04-25.

---

## 1. The x402 facilitator does not advertise Arc networks

**What happened.** `x402-express` v0.2.0 and the canonical
`https://x402.org/facilitator` host expect `network` values from an enum
that (today) enumerates `base-sepolia`, `base-mainnet`, and a handful of
others. Passing `arc-testnet` either silently returns 500 or is rejected
by the handshake. There is no documented contract for "how do I get *my*
chain onto an x402 facilitator?"

**Why it matters.** The *entire* sponsored track is **Agent-to-Agent
Payment Loop on Arc**. If the reference facilitator doesn't recognize the
sponsored chain out of the box, every team will silently fall back to
`X402_ENABLED=0` in the demo — which is exactly what we ended up doing.
That means the per-action pricing becomes a config literal, not a
measured payment, and nobody actually exercises the x402 primitive the
track is nominally about.

**What would land.** A **Circle-hosted x402 facilitator** at
`facilitator.arc.circle.com` (or similar) that:

- advertises `arc-testnet` + `arc-mainnet` in its `/supported` manifest,
- accepts EIP-3009 `transferWithAuthorization` signed by Circle Wallets,
- has one-line copy-pasteable snippets in both `x402-express` and
  `@x402/axios` README.

Half a day of DX work at Circle = 100% of hackathon teams actually using
x402. Big ROI.

---

## 2. There is no `@circle/nanopayments` SDK; everyone hand-rolls EIP-3009

**What happened.** The research path we took:
- Found the blog post announcing Nanopayments.
- Clicked through to `developers.circle.com/gateway/nanopayments`.
- Got docs that say "agents sign EIP-3009 `transferWithAuthorization`
  and POST to Gateway." Great.
- **No JavaScript/TypeScript SDK** wrapping this. No Python SDK. No
  published reference implementation of "signing EIP-3009 against USDC
  on Arc with the right EIP-712 domain separator."
- We ended up reading the EIP-3009 spec, writing a `signTypedData` call
  via viem, and constructing the domain by hand. That's a ~100-line
  subtle-bug minefield that every team will rebuild.

**What would land.** Ship `@circle/nanopay` and `circle-nanopay-py` with:

```ts
const auth = await wallet.signNanopayment({
  to: RECIPIENT, amount: '0.01', validAfter: 0, validBefore: 'in 10m',
})
await circle.nanopay.submit(auth)   // → tx hash when batched settlement lands
```

Even a **pure type-safe helper that only builds the EIP-712 payload**
would save teams a full day and eliminate "signed wrong domain separator,
tx rejected onchain" debugging. This is probably the single highest-ROI
fix on this list.

---

## 3. The USDC dual-decimal trap (18 native / 6 ERC-20) is a footgun

**What happened.** On Arc, **native USDC has 18 decimals** (because it's
the gas token), but the **ERC-20 contract at
`0x3600000000000000000000000000000000000000` uses 6 decimals** for
transfer/approve.

A 10^12× size error is one line of code away. We caught two of them
while building:

1. `executor_agent/main.py` initially had `"gasPrice": w3.to_wei("1","gwei")`
   copied from an Ethereum tutorial. On Arc that resolves to `10^9` in
   18-decimal USDC, which is `10^-9 USDC` — essentially zero. Silent
   under-pricing of gas.
2. Early draft of `bridge/src/arc.ts` had a helper that mixed
   `parseUnits(amount, 18)` with ERC-20 transfer calls. A $0.01 signal
   would have tried to transfer **$10,000,000,000.00** of USDC.

**What would land.**
- **Prominently warn** on every doc page that touches transfers. Not a
  footnote — a banner.
- Ship `parseUsdcERC20(amount)` and `parseUsdcNative(amount)` helpers in
  the official Circle SDK so users *don't reach for `parseUnits` at all*.
- Add a lint rule / runtime assertion in the reference templates that
  throws if a single tx mixes 18-dec native amounts with 6-dec ERC-20
  amounts.

This one footgun has cost the crypto industry billions of dollars
across various chains. It will happen again on Arc.

---

## 4. Entity Secret rotation pushes developers back to raw EOAs

**What happened.** Circle Wallets uses an **Entity Secret** that is
AES-encrypted against Circle's public key, **rotated per-call**. The
public key itself rotates on some cadence. This is a sound security
design, but:

- No official Node.js SDK example we found demonstrates the rotation
  correctly end-to-end.
- The Python SDK `circle-developer-controlled-wallets` has the logic
  but its examples cut off before showing the "sign an arbitrary typed
  data payload" leg needed for EIP-3009.
- The path of least resistance, as every demo video will show, is:
  **export a raw EOA private key, put it in `.env`, call it a day.**
  That defeats the entire Circle Wallets value prop.

**What would land.** A single, copy-pasteable end-to-end example titled
*"Sign EIP-712 typed data with a developer-controlled wallet"* in both
Node and Python, showing:

1. Create wallet via SDK.
2. Rotate Entity Secret correctly.
3. Submit a `signTypedData` request against an EIP-3009 payload.
4. Get back the signature, verify it matches what `eth_sign` would have
   produced for the same EOA.

Until that example exists, hackathon teams will route around Circle
Wallets and the track loses a core differentiator.

---

## 5. Developer Console should expose "copy as code" everywhere

**What happened.** The submission requires a **video moment** showing a
tx executed via the Circle Developer Console on Arc testnet. We did it.
It worked. But:

- After the tx landed, there was no obvious way to say *"okay, now run
  this same thing from my script."*
- No "copy as viem code" button. No "copy as Circle SDK call." No
  "export Postman collection."
- For an audience of developers, the Console UI currently feels like an
  end-state tool. It should feel like a **notebook**: every UI action
  has a backing API call that can be copied into a script.

**What would land.** Against every action in the Console UI:

- **"Copy as curl"** (already exists on some endpoints; make it universal)
- **"Copy as `@circle-developer/sdk` (Node)"**
- **"Copy as `circle-developer-controlled-wallets` (Python)"**
- **"Copy as viem / web3.py"** (for the on-chain call the Console just
  made on my behalf)

Bonus: a **"replay this tx from my agent"** button that literally copies
the signed payload, so a developer can demo-trace a production agent
reproducing a Console action.

---

## Summary

None of the five above are blockers to Arc adoption in the abstract.
They *are* blockers to **building an agent economy on Arc in a 5-day
hackathon**, which is the thing the track is trying to grow. In priority
order:

| Pain | Effort to fix | Hackathon impact |
|---|---|---|
| **1. x402 + arc-testnet** | Days | Unblocks the *entire* payment track |
| **2. `@circle/nanopay` SDK** | 1-2 weeks | Eliminates EIP-3009 hand-rolling |
| **3. Dual-decimal footgun helpers** | Days | Prevents silent 10^12× bugs |
| **4. Entity Secret rotation example** | Hours | Stops the EOA-leak shortcut |
| **5. Console "copy as code"** | Weeks | Turns Console from end-state to dev flow |

---

*Submitted as part of the Signal Mesh on Arc submission to the Circle
product team. Happy to expand on any of the above in a follow-up call.*
