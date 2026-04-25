"""
Demo driver — spins the full stack against the running bridge and produces
>= 50 premium signals (and ideally >= 50 on-chain settlement tx hashes).

Usage (three terminals):
    T1:  npm --prefix bridge run dev
    T2:  python -m demo.run_demo --symbols DOGE,XRP,SOL --duration 120

Inside, it:
  1. launches one dual-quote producer per symbol (subprocess, parquet replay)
  2. launches one meta_agent consumer
  3. launches one executor_agent (settles every premium signal)
  4. sleeps `duration` seconds, then prints a summary pulled from /health
     and /tx/recent so the screen recording captures a clean tally.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

# Windows consoles default to cp949/cp1252 and crash on em-dashes in --help.
# Force UTF-8 on stdout/stderr before argparse ever writes to them.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).parent.parent
BRIDGE = os.environ.get("ARC_BRIDGE_URL", "http://localhost:3000")


def _launch(cmd: list[str], logname: str) -> subprocess.Popen:
    logdir = ROOT / "demo" / "logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log_path = logdir / f"{logname}.log"
    f = open(log_path, "w", encoding="utf-8")
    print(f"  -> {logname}: {' '.join(cmd)}  (log: {log_path})")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
           "PYTHONUNBUFFERED": "1"}
    return subprocess.Popen(
        cmd, stdout=f, stderr=subprocess.STDOUT, cwd=ROOT,
        creationflags=flags, env=env,
    )


def _health() -> dict:
    try:
        r = requests.get(f"{BRIDGE}/health", timeout=3)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _tx() -> list[dict]:
    try:
        r = requests.get(f"{BRIDGE}/tx/recent", timeout=3)
        return r.json().get("tx", [])
    except Exception:
        return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="DOGE,XRP,SOL",
                    help="comma-separated symbols; each pair must exist in v1.3 backtest dir")
    ap.add_argument("--date", default="20260419")
    ap.add_argument("--speed", type=float, default=30.0)
    ap.add_argument("--threshold", type=float, default=0.0005,
                    help="demo threshold — lower than prod to guarantee signals")
    ap.add_argument("--duration", type=int, default=120,
                    help="seconds before summary + shutdown")
    ap.add_argument("--with-kimchi", action="store_true", default=True,
                    help="also launch the kimchi producer (synthetic KRW/USDT). "
                         "Default ON so the allocator's v1 lane has a live producer. "
                         "Pass --no-with-kimchi to skip.")
    ap.add_argument("--no-with-kimchi", dest="with_kimchi", action="store_false",
                    help="disable the kimchi producer (opt-out of v1 lane)")
    ap.add_argument("--kimchi-symbol", default="BTC")
    ap.add_argument("--with-funding", action="store_true", default=True,
                    help="launch the funding-rate producer (v3 lane). Default ON. "
                         "Demo cadence 30s. Pass --no-with-funding to skip.")
    ap.add_argument("--no-with-funding", dest="with_funding", action="store_false",
                    help="disable the funding producer (opt-out of v3 lane)")
    ap.add_argument("--funding-symbol", default="DOGE",
                    help="Symbol for funding producer (default DOGE, must be on Binance fapi)")
    ap.add_argument("--funding-cadence-sec", type=float, default=30.0,
                    help="Demo cadence for funding producer; prod is 8h=28800")
    ap.add_argument("--funding-demo-threshold", type=float, default=0.00002,
                    help="Demo entry-funding-rate threshold for v3. Production is "
                         "0.0005 (0.05%/8h ≈ 54%% APR), but at any given live moment "
                         "few of the 9 v1.3 coins clear that bar — so a 90s recording "
                         "would show v3=0 signals. Demo softens to 0.00002 (0.002%/8h) "
                         "so the v3 lane visibly emits during the demo window. "
                         "The dashboard's StrategyCards labels this as 'demo threshold'.")
    ap.add_argument("--pretrain-q", action="store_true",
                    help="run scripts/pretrain_q before launching the executor so the "
                         "Q-table boots warm (F3 cold-start mitigation). Skip if you "
                         "want to demonstrate learning-from-scratch.")
    ap.add_argument("--fee-rate", type=float, default=0.0005,
                    help="per-leg fee rate the producer applies to its edge filter. "
                         "Default 0.0005 = Bybit VIP 0 taker after USDC promo — matches "
                         "the pricing_policy fee model. Set to 0 only if you need the "
                         "producer to fire on *any* non-zero premium.")
    ap.add_argument("--hold-sec", type=float, default=30.0,
                    help="executor paper-position holding period; MUST match the "
                         "reward horizon the pretrainer was built against")
    ap.add_argument("--allocator-tick-sec", type=int, default=20,
                    help="capital allocator decision cadence for demo (prod=28800). "
                         "20s gives ~6 ticks per 2-min demo so the heat-map updates on camera.")
    ap.add_argument("--with-allocator", action="store_true", default=True,
                    help="launch capital_allocator consumer alongside meta/executor "
                         "(F3 — the v3 funding allocation lane). Default ON.")
    ap.add_argument("--with-regime-injector", action="store_true", default=True,
                    help="rotate ml/regime_override.json through populated Q-table "
                         "cells so Policy Heatmap + AllocatorCard show non-s8 activity "
                         "during the 2-min demo. Default ON. Honesty: this is a demo-only "
                         "aid — prod allocator (8h cadence) reads live Binance REST.")
    ap.add_argument("--regime-rotation",
                    default="s4,s2,s0,s5,s3,s7",
                    help="comma-separated regime keys to rotate through "
                         "(see demo/regime_injector.py RECIPES). Default hits all three "
                         "corner actions: ALL_V1 (s4/s5), ALL_V2 (s2/s3/s7), ALL_V3 (s0).")
    ap.add_argument("--regime-interval", type=int, default=12,
                    help="seconds between regime flips. 12s ≈ 1 flip per allocator-tick "
                         "at default 20s cadence, so the heatmap updates visibly.")
    args = ap.parse_args()

    # Sanity: bridge alive?
    try:
        requests.get(f"{BRIDGE}/health", timeout=2).raise_for_status()
    except Exception:
        print(f"[demo] bridge not reachable at {BRIDGE}. Start it first: npm --prefix bridge run dev")
        sys.exit(1)

    py = sys.executable

    if args.pretrain_q:
        print("[demo] pretraining Q-table (F3 cold-start fix)…")
        pre = subprocess.run(
            [py, "-m", "scripts.pretrain_q", "--episodes", "5000", "--warmup-per-cell", "50"],
            cwd=ROOT,
            capture_output=True, text=True, timeout=120,
        )
        if pre.returncode != 0:
            print(f"[demo] pretrain failed (exit {pre.returncode})")
            print(pre.stderr[-500:])
            sys.exit(1)
        # Print just the summary line so the demo log stays tidy
        for line in pre.stdout.splitlines():
            if "wrote Q-table" in line or "updates=" in line:
                print(f"  {line}")

    procs: list[subprocess.Popen] = []
    try:
        print("[demo] launching producers…")
        for sym in [s.strip() for s in args.symbols.split(",") if s.strip()]:
            procs.append(_launch(
                [py, "-m", "producers.dual_quote_agent.main",
                 "--symbol", sym, "--date", args.date,
                 "--speed", str(args.speed), "--threshold", str(args.threshold),
                 "--fee-rate", str(args.fee_rate), "--slippage-rate", "0"],
                f"producer_{sym}",
            ))
            time.sleep(0.4)

        if args.with_kimchi:
            print("[demo] launching kimchi producer (v1 lane, synthetic AR(1))…")
            procs.append(_launch(
                [py, "-m", "producers.kimchi_agent.main",
                 "--symbol", args.kimchi_symbol,
                 "--tick-interval", "1",
                 "--max-ticks", str(max(60, args.duration))],
                "producer_kimchi",
            ))
            time.sleep(0.5)

        if args.with_funding:
            print(
                f"[demo] launching funding producer (v3 lane, Binance fapi live, "
                f"demo entry threshold {args.funding_demo_threshold:.5f} = "
                f"{args.funding_demo_threshold*100:.4f}%/8h)…"
            )
            procs.append(_launch(
                [py, "-m", "producers.funding_agent.main",
                 "--symbol", args.funding_symbol,
                 "--live",
                 "--demo-cadence-sec", str(args.funding_cadence_sec),
                 "--entry-funding-rate", str(args.funding_demo_threshold),
                 "--max-duration-sec", str(max(60, args.duration))],
                "producer_funding",
            ))
            time.sleep(0.5)

        print("[demo] launching meta_agent…")
        procs.append(_launch([py, "-m", "consumers.meta_agent.main", "--interval", "3"], "meta"))
        time.sleep(1.0)

        print("[demo] launching executor_agent…")
        procs.append(_launch(
            [py, "-m", "consumers.executor_agent.main",
             "--interval", "3", "--settle-every", "1", "--settle-amount", "0.01",
             "--hold-sec", str(args.hold_sec)],
            "executor",
        ))

        if args.with_allocator:
            q_path = ROOT / "consumers" / "capital_allocator" / "allocator_q.json"
            if not q_path.exists():
                print(f"[demo] WARNING: {q_path} missing — skipping allocator. "
                      f"Run scripts/pretrain_allocator_q.py first.")
            else:
                print("[demo] launching capital_allocator…")
                procs.append(_launch(
                    [py, "-m", "consumers.capital_allocator.main",
                     "--q-table", str(q_path),
                     "--allocator-tick-seconds", str(args.allocator_tick_sec),
                     "--starting-book-usd", "50",
                     "--persist-every", "1",
                     "--verbose"],
                    "allocator",
                ))

                if args.with_regime_injector:
                    print("[demo] launching regime_injector (stub — demo-only) …")
                    procs.append(_launch(
                        [py, "-m", "demo.regime_injector",
                         "--rotation", args.regime_rotation,
                         "--interval", str(args.regime_interval),
                         "--verbose"],
                        "regime_injector",
                    ))

        print(f"[demo] running for {args.duration}s…")
        t0 = time.time()
        while time.time() - t0 < args.duration:
            time.sleep(5)
            h = _health()
            tx = _tx()
            print(
                f"  t+{int(time.time() - t0):>3}s  raw={h.get('signals',{}).get('raw',0):>3} "
                f"premium={h.get('signals',{}).get('premium',0):>3}  onchain_tx={len(tx)}"
            )
    finally:
        print("[demo] shutting down…")
        for p in procs:
            try:
                if os.name == "nt":
                    p.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                p.kill()

    tx = _tx()
    h = _health()
    try:
        econ = requests.get(f"{BRIDGE}/economics/summary", timeout=3).json()
    except Exception:
        econ = {}
    alloc_count = econ.get("allocation_count", 0)
    latest_alloc = econ.get("latest_allocation") or {}
    print("\n" + "=" * 60)
    print("DEMO SUMMARY")
    print("=" * 60)
    print(f"  raw signals    : {h.get('signals',{}).get('raw',0)}")
    print(f"  premium signals: {h.get('signals',{}).get('premium',0)}")
    print(f"  onchain tx     : {len(tx)}")
    print(f"  allocator ticks: {alloc_count}")
    if latest_alloc:
        w = latest_alloc.get("weights", {})
        print(f"  latest allocator: state={latest_alloc.get('state_idx')} "
              f"({latest_alloc.get('state_label','')}) action={latest_alloc.get('action_label')} "
              f"v1={w.get('v1',0):.2f} v2={w.get('v2',0):.2f} v3={w.get('v3',0):.2f}")
    if tx:
        print("  latest hashes  :")
        for row in tx[-5:]:
            print(f"    https://testnet.arcscan.app/tx/{row.get('hash')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
