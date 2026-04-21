"""
Executor Agent — consumes premium signals, pays via x402, paper-trades, and
settles a "fee" USDC transfer on Arc so the demo produces real on-chain tx
hashes for the submission video.

Flow per tick:
  1. GET {bridge}/signals/premium
     - if X402_ENABLED=1 on the bridge, this returns HTTP 402 + payment terms.
       We sign an EIP-3009 transferWithAuthorization via the Circle Wallet and
       retry with the X-Payment header.
     - if x402 is OFF (demo fallback), the endpoint returns signals directly.
  2. For each fresh premium signal, open a paper-trade position.
  3. Every N signals (default 5), perform a real USDC transfer on Arc testnet
     to an on-chain "treasury" address. This is the settlement tx that shows
     up in the demo video + Arc Explorer.

Run:
    python -m consumers.executor_agent.main --settle-every 1
"""
from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

from .pricing_policy import (
    FEE_ROUND_TRIP,
    PricingPolicy,
    state_index,
)

try:
    from web3 import Web3
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    WEB3_AVAILABLE = True
except Exception:
    WEB3_AVAILABLE = False


load_dotenv()

BRIDGE_URL = os.environ.get("ARC_BRIDGE_URL", "http://localhost:3000")
ARC_RPC = os.environ.get("ARC_RPC_URL", "https://rpc.testnet.arc.network")
ARC_CHAIN_ID = int(os.environ.get("ARC_CHAIN_ID", "5042002"))
USDC_ADDR = os.environ.get("USDC_ADDRESS", "0x3600000000000000000000000000000000000000")
EXECUTOR_PRIV = os.environ.get("EXECUTOR_PRIVATE_KEY", "")  # optional; Circle Wallet SDK alt
TREASURY = os.environ.get("TREASURY_ADDRESS", "")
NETWORK = os.environ.get("X402_NETWORK", "arc-testnet")

# EIP-3009 nanopay: the signer authorizes off-chain, a relayer (the
# "meta-agent" in our topology) submits on-chain. RELAYER_PRIVATE_KEY is the
# key that actually pays the tx gas on Arc. If it's unset, we fall back to
# having the executor self-submit its own authorization (still exercises the
# EIP-3009 code path, just without a separate relayer).
RELAYER_PRIV = os.environ.get("RELAYER_PRIVATE_KEY", "")
USDC_NAME = os.environ.get("USDC_CONTRACT_NAME", "USD Coin")
USDC_VERSION = os.environ.get("USDC_CONTRACT_VERSION", "2")

USDC_ABI = [
    {
        "type": "function",
        "name": "transfer",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [{"type": "bool"}],
    },
    {
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"type": "uint256"}],
    },
    # EIP-3009 Nanopayment — signer authorizes, any relayer submits.
    # Circle's USDC implements this; it is the on-chain primitive behind
    # x402 and the "meta-agent pays gas on behalf of the agent" pattern.
    {
        "type": "function",
        "name": "transferWithAuthorization",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"},
        ],
        "outputs": [],
    },
]


@dataclass
class Position:
    symbol: str
    action: str
    entry_premium: float
    notional_usd: float
    opened_at: float
    producer_id: str = "unknown"
    signal_ts: float = 0.0
    expected_pnl: float = 0.0
    # Q-learning state carried from the pricing decision at entry time.
    state_idx: int = 0
    action_idx: int = 1
    price_paid: float = 0.0          # what the executor actually paid the meta
    base_price: float = 0.0          # fee-covered anchor the multiplier scaled
    realized_edge_rate: float = 0.0  # realized premium captured, post-hold
    pnl_usd: float = 0.0             # final net PnL (after fees + price_paid)
    exit_premium: Optional[float] = None
    closed: bool = False


@dataclass
class ExecutorState:
    positions: list[Position] = field(default_factory=list)
    paid_usdc: float = 0.0
    settled_tx: list[str] = field(default_factory=list)
    outcomes_reported: int = 0
    net_pnl_cumulative: float = 0.0


# ── Allocator integration (§7.3) ────────────────────────────────────────
# Map producer_id → strategy slot key in the allocator's weights payload.
# v1=kimchi, v2=dual_quote, v3=funding — matches ALLOCATOR_RL_DESIGN.md §0.
PRODUCER_STRATEGY_MAP = {
    "kimchi_agent": "v1",
    "dual_quote_agent": "v2",
    "funding_agent": "v3",
}


@dataclass
class AllocationView:
    """Cached /allocation response. Keeps executor decoupled from allocator uptime."""
    weights: dict = field(default_factory=lambda: {"v1": 1.0, "v2": 1.0, "v3": 1.0})
    v3_offset_sec: int = 0
    notional_scalar: float = 1.0
    frozen: bool = False
    frozen_reason: Optional[str] = None
    tick_id: Optional[str] = None
    last_fetch_at: float = 0.0


def _fetch_allocation(view: AllocationView) -> None:
    """Pull latest /allocation and refresh view. Silent on failure — executor
    keeps pre-existing weights so a transient allocator blip doesn't force
    every signal to open at zero size."""
    try:
        r = requests.get(f"{BRIDGE_URL}/allocation", timeout=2)
        if not r.ok:
            return
        body = r.json()
        if not body or body.get("tick_id") in (None, view.tick_id):
            return
        w = body.get("weights") or {}
        if not all(k in w for k in ("v1", "v2", "v3")):
            return
        view.weights = {"v1": float(w["v1"]), "v2": float(w["v2"]), "v3": float(w["v3"])}
        # Bridge strips these optional fields (see bridge/src/index.ts:395) —
        # they'll be absent until F-follow-up patches the whitelist.
        view.v3_offset_sec = int(body.get("v3_entry_offset_sec", 0) or 0)
        view.notional_scalar = float(body.get("notional_scalar", 1.0) or 1.0)
        view.frozen = bool(body.get("allocation_frozen", False))
        view.frozen_reason = body.get("frozen_reason")
        view.tick_id = body.get("tick_id")
    except Exception:
        pass


def _allocator_weight(view: AllocationView, producer_id: str) -> float:
    slot = PRODUCER_STRATEGY_MAP.get(producer_id)
    if slot is None:
        return 1.0  # unknown producer (e.g. meta-agent passthrough) → full size
    return float(view.weights.get(slot, 1.0))


def _build_x402_payment_header(challenge: dict, w3: "Web3", signer) -> Optional[str]:
    """Respond to an x402 HTTP 402 challenge by signing a
    TransferWithAuthorization and returning a base64-encoded X-Payment header.

    The x402 spec wraps the EIP-3009 auth struct in a versioned JSON envelope;
    the facilitator submits it on-chain to settle, then lets the request
    through. See https://x402.org for the envelope shape.
    """
    import base64
    try:
        accepts = challenge.get("accepts") or []
        if not accepts:
            return None
        option = accepts[0]
        pay_to = option.get("payTo") or option.get("recipient")
        max_amt = int(option.get("maxAmountRequired") or option.get("maxAmount") or 0)
        asset = option.get("asset") or USDC_ADDR
        if not pay_to or max_amt <= 0:
            return None
        auth = _sign_transfer_with_authorization(
            signer, pay_to, max_amt, ARC_CHAIN_ID, asset
        )
        payload = {
            "x402Version": int(challenge.get("x402Version") or 1),
            "scheme": option.get("scheme") or "exact",
            "network": option.get("network") or NETWORK,
            "payload": {
                "signature": {
                    "v": auth["v"],
                    "r": "0x" + auth["r"].hex(),
                    "s": "0x" + auth["s"].hex(),
                },
                "authorization": {
                    "from": auth["from"],
                    "to": auth["to"],
                    "value": str(auth["value"]),
                    "validAfter": auth["validAfter"],
                    "validBefore": auth["validBefore"],
                    "nonce": auth["nonce"],
                },
            },
        }
        return base64.b64encode(json.dumps(payload).encode()).decode()
    except Exception as e:
        print(f"[exec] x402 header build fail: {e}", file=sys.stderr)
        return None


def _http_get_premium(w3: Optional["Web3"] = None, signer=None) -> list[dict]:
    try:
        r = requests.get(f"{BRIDGE_URL}/signals/premium", timeout=5)
        if r.status_code == 402:
            # x402 challenge — sign an EIP-3009 auth and retry
            if w3 is None or signer is None:
                print("[exec] bridge returned 402 but signer disabled — skipping")
                return []
            try:
                challenge = r.json()
            except Exception:
                challenge = {}
            header = _build_x402_payment_header(challenge, w3, signer)
            if not header:
                print("[exec] could not build X-Payment header")
                return []
            r2 = requests.get(
                f"{BRIDGE_URL}/signals/premium",
                headers={"X-Payment": header},
                timeout=8,
            )
            if not r2.ok:
                print(f"[exec] x402 retry failed: {r2.status_code}")
                return []
            settle = r2.headers.get("X-Payment-Response", "")
            if settle:
                print(f"[exec] x402 settled ← {settle[:40]}…")
            return r2.json().get("signals", [])
        r.raise_for_status()
        return r.json().get("signals", [])
    except Exception as e:
        print(f"[exec] fetch fail: {e}", file=sys.stderr)
        return []


def _settle_usdc(w3: "Web3", account, amount_usdc: float = 0.01) -> Optional[str]:
    """ERC-20 leg uses 6 decimals; native USDC gas uses 18. Ask the RPC for gas
    price instead of hardcoding gwei literals — `gwei` only makes sense on ETH
    chains, not on Arc (where USDC is the native 18-dec gas token)."""
    if TREASURY == "" or account is None:
        return None
    try:
        c = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDR), abi=USDC_ABI)
        amount_units = int(round(amount_usdc * 1_000_000))  # 6-decimal ERC-20 leg
        nonce = w3.eth.get_transaction_count(account.address)
        # Arc native USDC has 18 decimals — use eth_gasPrice from RPC, don't
        # hardcode "1 gwei" (that would be 10^-9 USDC, essentially zero).
        try:
            gas_price = w3.eth.gas_price
        except Exception:
            gas_price = 10**9  # 1e-9 native USDC fallback (dev env only)
        tx = c.functions.transfer(
            Web3.to_checksum_address(TREASURY), amount_units
        ).build_transaction(
            {
                "from": account.address,
                "chainId": ARC_CHAIN_ID,
                "nonce": nonce,
                "gas": 100_000,
                "gasPrice": gas_price,
            }
        )
        signed = account.sign_transaction(tx)
        # web3.py v7 renamed `rawTransaction` → `raw_transaction`
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        # Wait briefly for receipt so the video shows confirmed tx, not pending
        try:
            w3.eth.wait_for_transaction_receipt(h, timeout=20)
        except Exception:
            pass  # don't block forever; the hash is still reportable
        return h.hex()
    except Exception as e:
        print(f"[exec] settle fail: {e}", file=sys.stderr)
        return None


def _sign_transfer_with_authorization(
    account,
    to_addr: str,
    value_units: int,
    chain_id: int,
    usdc_addr: str,
    valid_seconds: int = 600,
) -> dict:
    """Build and sign an EIP-3009 TransferWithAuthorization typed data struct.

    Returns the payload a relayer needs to submit the on-chain call, including
    the random 32-byte `nonce` (which is NOT the account nonce — it's a
    replay-protection salt, unique per authorization).
    """
    now = int(time.time())
    nonce = "0x" + secrets.token_hex(32)
    typed = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": USDC_NAME,
            "version": USDC_VERSION,
            "chainId": chain_id,
            "verifyingContract": Web3.to_checksum_address(usdc_addr),
        },
        "message": {
            "from": account.address,
            "to": Web3.to_checksum_address(to_addr),
            "value": value_units,
            "validAfter": 0,
            "validBefore": now + valid_seconds,
            "nonce": nonce,
        },
    }
    encoded = encode_typed_data(full_message=typed)
    signed = account.sign_message(encoded)
    return {
        "from": account.address,
        "to": Web3.to_checksum_address(to_addr),
        "value": value_units,
        "validAfter": 0,
        "validBefore": now + valid_seconds,
        "nonce": nonce,
        "v": signed.v,
        "r": signed.r.to_bytes(32, "big"),
        "s": signed.s.to_bytes(32, "big"),
    }


def _settle_usdc_nanopay(
    w3: "Web3",
    signer,
    relayer,
    amount_usdc: float = 0.01,
) -> Optional[str]:
    """EIP-3009 nanopayment leg: signer authorizes, relayer submits on Arc.

    This is the path the Circle/x402 facilitator uses in production. Running
    it in the demo proves the marketplace is actually gasless for the agent
    that emits the payment — the relayer eats the gas (which, on Arc, is also
    USDC, so the whole economy stays in a single unit of account).
    """
    if signer is None or relayer is None or TREASURY == "":
        return None
    try:
        c = w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDR), abi=USDC_ABI
        )
        amount_units = int(round(amount_usdc * 1_000_000))
        auth = _sign_transfer_with_authorization(
            signer,
            TREASURY,
            amount_units,
            ARC_CHAIN_ID,
            USDC_ADDR,
        )
        try:
            gas_price = w3.eth.gas_price
        except Exception:
            gas_price = 10**9
        nonce = w3.eth.get_transaction_count(relayer.address)
        tx = c.functions.transferWithAuthorization(
            auth["from"],
            auth["to"],
            auth["value"],
            auth["validAfter"],
            auth["validBefore"],
            auth["nonce"],
            auth["v"],
            auth["r"],
            auth["s"],
        ).build_transaction(
            {
                "from": relayer.address,
                "chainId": ARC_CHAIN_ID,
                "nonce": nonce,
                "gas": 200_000,
                "gasPrice": gas_price,
            }
        )
        signed = relayer.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        h = w3.eth.send_raw_transaction(raw)
        try:
            w3.eth.wait_for_transaction_receipt(h, timeout=20)
        except Exception:
            pass
        return h.hex()
    except Exception as e:
        print(f"[exec] nanopay fail: {e}", file=sys.stderr)
        return None


def _notify_bridge_tx(tx_hash: str, amount: float) -> None:
    try:
        requests.post(
            f"{BRIDGE_URL}/tx/report",
            json={"hash": tx_hash, "amount": amount},
            timeout=3,
        )
    except Exception:
        pass


def _open_position(s: dict, state: ExecutorState, decision) -> None:
    """Open a paper position carrying the pricing decision that produced it.

    The Q-learning loop needs (state_idx, action_idx, price_paid) at close time
    so it can credit the right cell. We stash them on the Position rather than
    a parallel dict — that way if the executor crashes mid-flight, nothing
    desyncs.
    """
    pos = Position(
        symbol=s.get("symbol", "UNK"),
        action=s.get("action", "HOLD"),
        entry_premium=float(s.get("premium_rate", 0.0)),
        notional_usd=float(s.get("notional_usd") or 100.0),
        opened_at=time.time(),
        producer_id=str(s.get("producer_id", "unknown")),
        signal_ts=float(s.get("timestamp", 0)),
        expected_pnl=float(s.get("expected_profit_usd") or 0.0),
        state_idx=decision.state_idx,
        action_idx=decision.action_idx,
        price_paid=decision.price_usdc,
        base_price=decision.base_price,
    )
    state.positions.append(pos)


def _report_outcome(pos: Position) -> bool:
    """Ship realized PnL + the fee-persona bookkeeping back to the bridge.

    `realized_edge_rate` lets the meta agent distinguish between "the producer
    was wrong about direction" and "the producer was right but the executor
    overpaid for the signal" — two failure modes with very different fixes.
    """
    try:
        r = requests.post(
            f"{BRIDGE_URL}/signals/outcome",
            json={
                "producer_id": pos.producer_id,
                "symbol": pos.symbol,
                "action": pos.action,
                "signal_ts": pos.signal_ts,
                "pnl_usd": pos.pnl_usd,
                # Extended fields so bridge can surface net-of-fee economics.
                "realized_edge_rate": pos.realized_edge_rate,
                "notional_usd": pos.notional_usd,
                "price_paid_usdc": pos.price_paid,
                "entry_premium": pos.entry_premium,
            },
            timeout=3,
        )
        return r.ok
    except Exception:
        return False


def _simulate_realized_edge(entry_premium: float) -> float:
    """Sample realized edge without leaking the meta agent's own optimism.

    Overdeck's rule applies: never train against a target that already contains
    the predictor you're evaluating. The old implementation used
    `expected_pnl × decay + noise × |expected_pnl|`, which let a confidently-
    wrong meta inflate realized PnL — the Q table would then reward the
    executor for following bad meta advice.

    Here, realized edge is drawn from an entry-premium-anchored distribution
    whose mean is a haircut of |entry_premium| (not expected_pnl), with a
    random signed retention factor. For the demo this is an honest stand-in
    for "replay the next 30s of the parquet and see whether the spread
    actually closed or widened" — the production-grade path.
    """
    # Spread-mean-reversion retention: uniform [0.35, 1.05] of entry premium.
    # The 1.05 upper lets rare favorable drifts register as over-capture.
    retention = random.uniform(0.35, 1.05)
    # 35% of the time we get adverse selection: realized direction flips.
    sign = 1.0 if random.random() > 0.35 else -1.0
    mag = abs(entry_premium) * retention
    # Add a small iid noise floor proportional to 1 bp so the cell Q values
    # don't converge to perfectly deterministic estimates.
    noise = random.gauss(0.0, 0.0001)
    return sign * mag + noise


def _close_ready_positions(
    state: ExecutorState,
    hold_sec: float,
    policy: PricingPolicy,
) -> int:
    """Close positions whose hold time elapsed, compute honest realized PnL,
    update the Q-table, and ship the outcome to the bridge.

    Realized PnL accounting (after Overdeck's target-leakage fix):
        gross_pnl   = realized_edge_rate × notional
        round_trip_fee = FEE_ROUND_TRIP × notional
        net_pnl     = gross_pnl - round_trip_fee - price_paid

    `net_pnl` is what the Q cell learns against. This is the single signal
    that makes the pricing model converge on "charge enough to recover fees
    + expected edge haircut" instead of "charge whatever the meta thinks this
    is worth" (which would pollute every cell with meta's systematic errors).
    """
    now = time.time()
    closed = 0
    for pos in state.positions:
        if pos.closed or (now - pos.opened_at) < hold_sec:
            continue
        realized_edge = _simulate_realized_edge(pos.entry_premium)
        gross = realized_edge * pos.notional_usd
        fee_cost = FEE_ROUND_TRIP * pos.notional_usd
        net = gross - fee_cost - pos.price_paid
        pos.realized_edge_rate = realized_edge
        pos.pnl_usd = round(net, 4)
        pos.exit_premium = pos.entry_premium  # demo shortcut; real path replays bars
        pos.closed = True
        state.net_pnl_cumulative += pos.pnl_usd
        # Credit the pricing cell whose action opened this position.
        policy.update(
            state_idx=pos.state_idx,
            action_idx=pos.action_idx,
            realized_pnl=pos.pnl_usd,
            accepted=True,
        )
        if _report_outcome(pos):
            state.outcomes_reported += 1
        closed += 1
    return closed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle-every", type=int, default=1, help="settle 1 real USDC tx per N signals")
    ap.add_argument("--interval", type=float, default=4.0)
    ap.add_argument("--settle-amount", type=float, default=0.01,
                    help="cap on per-signal settlement (variable price floor/cap)")
    ap.add_argument("--settle-floor", type=float, default=0.0005,
                    help="min per-signal settlement (matches raw tier price)")
    ap.add_argument("--hold-sec", type=float, default=30.0,
                    help="paper position holding period before realized outcome is reported. "
                         "Default matches the Q-learning reward horizon — credit assignment "
                         "integrity (Sutton/Barto F2) breaks if this drifts from the horizon "
                         "the offline pretrainer assumed.")
    ap.add_argument("--nanopay", action="store_true",
                    help="use EIP-3009 transferWithAuthorization (gasless for signer) "
                         "instead of plain ERC-20 transfer. Requires RELAYER_PRIVATE_KEY.")
    ap.add_argument("--q-table", default=str(Path(__file__).parent / "q_table.json"),
                    help="path to persisted Q-table (loaded on boot, saved on shutdown "
                         "and every 100 updates)")
    ap.add_argument("--no-persist-q", action="store_true",
                    help="run with a fresh Q table every session — useful for ablation")
    args = ap.parse_args()

    q_path = None if args.no_persist_q else Path(args.q_table)
    policy = PricingPolicy(stats_path=q_path, load=not args.no_persist_q)

    w3 = None
    account = None
    relayer = None
    if WEB3_AVAILABLE and EXECUTOR_PRIV and TREASURY:
        w3 = Web3(Web3.HTTPProvider(ARC_RPC))
        try:
            account = Account.from_key(EXECUTOR_PRIV)
            bal = w3.eth.get_balance(account.address)
            print(f"[exec] onchain ON — addr={account.address} native_bal_wei={bal}")
            if args.nanopay:
                relayer_key = RELAYER_PRIV or EXECUTOR_PRIV
                relayer = Account.from_key(relayer_key)
                same = relayer.address.lower() == account.address.lower()
                print(
                    f"[exec] nanopay ON (EIP-3009) — relayer={relayer.address}"
                    + (" [self-relay: set RELAYER_PRIVATE_KEY for true split]" if same else "")
                )
        except Exception as e:
            print(f"[exec] onchain disabled: {e}", file=sys.stderr)
            w3 = None
    else:
        print("[exec] onchain OFF — EXECUTOR_PRIVATE_KEY or TREASURY_ADDRESS unset (paper only)")

    state = ExecutorState()
    alloc_view = AllocationView()
    seen_ts: set[float] = set()
    processed = 0

    try:
        while True:
            # Refresh allocator weights before each poll. The allocator ticks
            # on its own cadence (30s demo / 8h prod); this fetch is cheap and
            # also surfaces §5.5 DRAWDOWN_RAIL notional_scalar if fired.
            _fetch_allocation(alloc_view)
            prems = _http_get_premium(w3, account)
            for s in prems:
                ts = float(s.get("timestamp", 0))
                if ts in seen_ts:
                    continue
                seen_ts.add(ts)
                # Q-learning pricing: the multiplier is chosen per state so
                # the price responds to (regime × edge), not to meta's own
                # expected_pnl (F5: confidence is intentionally NOT in state).
                notional = float(s.get("notional_usd") or 100.0)
                premium_rate = float(s.get("premium_rate") or 0.0)
                decision = policy.choose_price(premium_rate, notional)

                # §7.3 allocator scaling: multiply notional by weights[producer_id].
                # weight 0 → zero-size paper position (still pay the signal price
                # so marketplace economics stay intact). notional_scalar applies
                # §5.5 drawdown cut on top.
                producer_id = str(s.get("producer_id", "unknown"))
                w_slot = _allocator_weight(alloc_view, producer_id)
                effective_notional = notional * w_slot * alloc_view.notional_scalar
                muted = w_slot == 0.0
                if muted:
                    s = {**s, "notional_usd": 0.0, "allocator_muted": True}
                else:
                    s = {**s, "notional_usd": effective_notional}

                # §5.6 v3 entry offset: defer OPEN for v3 signals by N seconds.
                # In demo mode (cadence=30), offset auto-scales to ~0s.
                if (
                    alloc_view.v3_offset_sec > 0
                    and PRODUCER_STRATEGY_MAP.get(producer_id) == "v3"
                    and not muted
                ):
                    print(
                        f"[exec] v3 entry deferred +{alloc_view.v3_offset_sec}s "
                        f"(§5.6 funding-boundary crowding mitigation)"
                    )
                    time.sleep(alloc_view.v3_offset_sec)

                _open_position(s, state, decision)
                price = decision.price_usdc
                state.paid_usdc += price
                processed += 1

                if processed % args.settle_every == 0:
                    if w3 is None:
                        h = None
                    elif args.nanopay and relayer is not None:
                        h = _settle_usdc_nanopay(w3, account, relayer, price)
                    else:
                        h = _settle_usdc(w3, account, price)
                    if h:
                        state.settled_tx.append(h)
                        _notify_bridge_tx(h, price)
                        path = "nanopay" if args.nanopay else "transfer"
                        print(
                            f"[exec] {path} priced ${price:.5f} USDC "
                            f"(conf={s.get('confidence_score'):.2f}) "
                            f"→ https://testnet.arcscan.app/tx/{h}"
                        )
                    else:
                        print(
                            f"[exec] paper-settle price=${price:.5f}. signals={processed} "
                            f"paid=${state.paid_usdc:.4f} "
                            f"pnl=${sum(p.pnl_usd for p in state.positions):.3f}"
                        )

            # Close any held positions whose hold-time elapsed, feeding
            # the outcome loop so the meta agent can price producer reliability.
            closed = _close_ready_positions(state, args.hold_sec, policy)
            if closed:
                print(
                    f"[exec] closed {closed} positions → outcomes reported={state.outcomes_reported} "
                    f"net_pnl=${state.net_pnl_cumulative:.3f}"
                )
                # Flush the Q table occasionally so a crash doesn't eat learning.
                if policy.stats.total_updates % 100 == 0:
                    policy.save()

            if len(seen_ts) > 5000:
                seen_ts.clear()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pnl = sum(p.pnl_usd for p in state.positions)
        print(
            f"\n[exec] stopped. positions={len(state.positions)} "
            f"paid=${state.paid_usdc:.3f} pnl=${pnl:.3f} "
            f"net_pnl=${state.net_pnl_cumulative:.3f} "
            f"onchain_tx={len(state.settled_tx)} "
            f"q_updates={policy.stats.total_updates}"
        )
        if state.settled_tx:
            print("recent tx hashes:")
            for h in state.settled_tx[-10:]:
                print(f"  https://testnet.arcscan.app/tx/{h}")
        policy.save()


if __name__ == "__main__":
    main()
