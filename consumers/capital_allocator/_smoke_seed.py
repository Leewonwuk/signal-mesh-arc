"""Seed bridge with kimchi+dual_quote signals and a few past-tick PnLs so the
allocator (run right after this) gets a non-cold state AND finds reward for
its PREVIOUS tick on the 2nd iteration.

Usage: python consumers/capital_allocator/_smoke_seed.py
Then immediately: python -m consumers.capital_allocator.main --allocator-tick-seconds 10 ...
"""
import math
import random
import time
import requests

BRIDGE = "http://localhost:3000"
CADENCE = 10


def post(path, body):
    r = requests.post(f"{BRIDGE}{path}", json=body, timeout=3)
    return r.status_code, r.text[:80]


# 1) Seed kimchi + dual_quote signals so /signals/latest returns fresh entries.
now = time.time()
print(post("/signals/publish", {
    "producer_id": "kimchi_agent",
    "strategy": "kimchi_premium",
    "symbol": "BTC",
    "action": "OPEN",
    "premium_rate": 0.006,          # 60 bp → wide dislocation
    "tier": "raw",
    "reason": "smoke-seed",
    "timestamp": now,
}))
print(post("/signals/publish", {
    "producer_id": "dual_quote_agent",
    "strategy": "usdt_usdc",
    "symbol": "BTC",
    "action": "OPEN",
    "premium_rate": 0.0009,         # 9 bp → above 0.0008 usdc_p50
    "tier": "raw",
    "reason": "smoke-seed",
    "timestamp": now,
}))

# 2) Seed tick_pnl for the next THREE cadence-aligned ticks so the allocator's
#    2nd/3rd ticks find complete reward for their PREVIOUS tick.
base_tick = math.floor(now / CADENCE) * CADENCE
for offset in (0, 1, 2):
    tick_epoch = base_tick + offset * CADENCE
    iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(tick_epoch))
    for strat, seed in (("v1", offset * 11), ("v2", offset * 13), ("v3", offset * 17)):
        random.seed(seed + offset)
        pnl = round(random.uniform(-0.2, 0.4), 4)
        code, _ = post("/strategy/tick_pnl", {
            "tick_id": iso,
            "strategy": strat,
            "ts": iso,
            "realized_pnl_usd": pnl,
            "notional_usd": 500.0,
            "n_trades": 2,
        })
        print(f"tick_pnl {iso} {strat} ${pnl:+.4f} -> {code}")

print("seed done.")
