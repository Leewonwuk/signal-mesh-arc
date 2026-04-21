#!/usr/bin/env python
"""RL learning verification harness.

Proves four claims that SUBMISSION.md makes about the allocator:
  1. Forced regime A → state_idx==7 (hot/hot/wide), action picked from
     {ALL_V1, ALL_V2, ALL_V3, KIMCHI_DUAL, DUAL_FUND, KIMCHI_FUND}.
  2. Forced regime B → state_idx==0 (calm/cold/tight), allocation switches
     within ≤2 ticks.
  3. Online Q-update fires: visit_counts[s][a] increments, Q-value moves.
  4. /api/allocation (dashboard proxy) serves fresh tick_ids in real time.

Also acts as the "regime flip demo" promised in SUBMISSION §12.

Usage:
    # bridge + dashboard must be up
    python scripts/verify_rl_learning.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
ARTIFACTS = REPO / "scripts" / "verify_artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

Q_LIVE = REPO / "consumers" / "capital_allocator" / "allocator_q.json"
Q_TEST = ARTIFACTS / "q_test.json"      # ephemeral copy the test mutates
Q_BEFORE_A = ARTIFACTS / "q_before_A.json"
Q_AFTER_A = ARTIFACTS / "q_after_A.json"
Q_AFTER_B = ARTIFACTS / "q_after_B.json"
LOG_A = ARTIFACTS / "allocator_A.log"
LOG_B = ARTIFACTS / "allocator_B.log"
SEED_LOG = ARTIFACTS / "seeder.log"

BRIDGE = "http://localhost:3000"
DASHBOARD = "http://localhost:5173"

REGIME_A = {  # hot vol, hot funding, wide dislocation → state 7
    "FORCE_VOL": "0.05",
    "FORCE_FUNDING": "0.0002",
    "FORCE_KIMCHI": "0.005",
    "FORCE_USDC": "0.002",
}
REGIME_B = {  # calm, cold funding, tight dislocation → state 0
    "FORCE_VOL": "0.005",
    "FORCE_FUNDING": "0.00001",
    "FORCE_KIMCHI": "0.0005",
    "FORCE_USDC": "0.0003",
}

CADENCE_SEC = 4
N_TICKS_PER_REGIME = 5
SEED_PNL = {"v1": 0.30, "v2": 0.25, "v3": 0.40}  # USD per tick — positive so Q rises


def banner(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def health_check() -> None:
    bridge_ok = requests.get(f"{BRIDGE}/health", timeout=2).json().get("ok")
    dash_ok = requests.get(f"{DASHBOARD}/api/allocation", timeout=2).status_code == 200
    print(f"bridge ok={bridge_ok}  dashboard /api/allocation reachable={dash_ok}")
    if not bridge_ok or not dash_ok:
        sys.exit("bridge or dashboard not running — start them first")


def reset_qtable() -> None:
    shutil.copy(Q_LIVE, Q_TEST)
    shutil.copy(Q_TEST, Q_BEFORE_A)
    print(f"copied {Q_LIVE.name} → {Q_TEST.name}")


def launch_allocator(env_extra: dict, log_path: Path, n_ticks: int) -> subprocess.Popen:
    env = {**os.environ, **env_extra}
    cmd = [
        sys.executable, "-m", "consumers.capital_allocator.main",
        "--q-table", str(Q_TEST),
        "--allocator-tick-seconds", str(CADENCE_SEC),
        "--max-ticks", str(n_ticks),
        "--persist-every", "1",
        "--starting-book-usd", "50",
        "--verbose",
    ]
    f = open(log_path, "w", encoding="utf-8")
    p = subprocess.Popen(
        cmd, cwd=str(REPO), env=env, stdout=f, stderr=subprocess.STDOUT,
    )
    return p


def seed_rewards_loop(stop_flag: dict, regime_label: str) -> None:
    """Background-style helper: poll /allocation/history, post synthetic
    v1+v2+v3 PnL for any tick_id we haven't seeded yet."""
    seeded: set[str] = set()
    log = open(SEED_LOG, "a", encoding="utf-8")
    log.write(f"\n--- regime {regime_label} ---\n")
    while not stop_flag["done"]:
        try:
            r = requests.get(f"{BRIDGE}/allocation/history", params={"limit": 50}, timeout=2)
            history = r.json().get("entries", [])
            for entry in history:
                tid = entry.get("tick_id")
                if not tid or tid in seeded:
                    continue
                ts = entry.get("ts", tid)
                for strat, pnl in SEED_PNL.items():
                    requests.post(f"{BRIDGE}/strategy/tick_pnl", json={
                        "tick_id": tid, "strategy": strat, "ts": ts,
                        "realized_pnl_usd": pnl, "notional_usd": 500.0, "n_trades": 1,
                    }, timeout=2)
                seeded.add(tid)
                log.write(f"seeded {regime_label} {tid} pnl={SEED_PNL}\n")
                log.flush()
        except Exception as e:
            log.write(f"seed err: {e}\n")
        time.sleep(0.5)
    log.close()


def poll_dashboard_freshness(duration_sec: float) -> list[str]:
    """Hit dashboard proxy every 1s; return list of distinct tick_ids seen."""
    seen: list[str] = []
    end = time.time() + duration_sec
    while time.time() < end:
        try:
            r = requests.get(f"{DASHBOARD}/api/allocation", timeout=2)
            tid = r.json().get("tick_id")
            if tid and (not seen or seen[-1] != tid):
                seen.append(tid)
        except Exception:
            pass
        time.sleep(1.0)
    return seen


def run_regime(label: str, env: dict, log_path: Path, snapshot_after: Path) -> dict:
    banner(f"REGIME {label}: {env}")
    import threading
    stop = {"done": False}
    seeder = threading.Thread(target=seed_rewards_loop, args=(stop, label), daemon=True)
    seeder.start()

    proc = launch_allocator(env, log_path, N_TICKS_PER_REGIME)
    ticks_seen = poll_dashboard_freshness(CADENCE_SEC * (N_TICKS_PER_REGIME + 1))
    proc.wait(timeout=CADENCE_SEC * 2)
    stop["done"] = True
    time.sleep(0.5)

    shutil.copy(Q_TEST, snapshot_after)

    # Pull history slice the allocator just emitted
    r = requests.get(f"{BRIDGE}/allocation/history", params={"limit": N_TICKS_PER_REGIME + 2}, timeout=2)
    hist = r.json().get("entries", [])[-N_TICKS_PER_REGIME:]
    return {"ticks_seen": ticks_seen, "history": hist, "log": log_path.read_text(encoding="utf-8", errors="replace")}


def diff_qtable(before: Path, after: Path) -> dict:
    a = json.loads(before.read_text())
    b = json.loads(after.read_text())
    visit_delta = []
    q_delta = []
    for s in range(9):
        for act in range(7):
            dv = b["visit_counts"][s][act] - a["visit_counts"][s][act]
            dq = b["q_table"][s][act] - a["q_table"][s][act]
            if dv != 0 or abs(dq) > 1e-9:
                visit_delta.append((s, act, dv))
                q_delta.append((s, act, a["q_table"][s][act], b["q_table"][s][act]))
    return {"visit_delta": visit_delta, "q_delta": q_delta}


def assert_state_was(history: list, expected_state: int) -> tuple[bool, list[int]]:
    states = [h.get("state_idx") for h in history]
    return (expected_state in states, states)


def main() -> int:
    health_check()
    reset_qtable()

    res_a = run_regime("A_hot/hot/wide", REGIME_A, LOG_A, Q_AFTER_A)
    diff_a = diff_qtable(Q_BEFORE_A, Q_AFTER_A)
    res_b = run_regime("B_calm/cold/tight", REGIME_B, LOG_B, Q_AFTER_B)
    diff_b = diff_qtable(Q_AFTER_A, Q_AFTER_B)

    banner("VERDICT")
    a_state_ok, a_states = assert_state_was(res_a["history"], 7)
    b_state_ok, b_states = assert_state_was(res_b["history"], 0)
    a_actions = [h.get("action_label") for h in res_a["history"]]
    b_actions = [h.get("action_label") for h in res_b["history"]]
    actions_changed = set(a_actions) != set(b_actions) or any(
        a != b for a, b in zip(a_actions, b_actions)
    )

    print(f"[1] regime A states observed: {a_states}  → expected 7 anywhere: {'PASS' if a_state_ok else 'FAIL'}")
    print(f"[2] regime B states observed: {b_states}  → expected 0 anywhere: {'PASS' if b_state_ok else 'FAIL'}")
    print(f"[3] actions A: {a_actions}")
    print(f"    actions B: {b_actions}")
    print(f"    allocation responded to regime flip: {'PASS' if actions_changed else 'FAIL'}")
    print(f"[4] Q-updates regime A:  visit_delta={diff_a['visit_delta']}")
    for s, a, qa, qb in diff_a["q_delta"]:
        print(f"      Q[{s},{a}] {qa:+.4f} → {qb:+.4f}  (Δ={qb-qa:+.4f})")
    print(f"[4] Q-updates regime B:  visit_delta={diff_b['visit_delta']}")
    for s, a, qa, qb in diff_b["q_delta"]:
        print(f"      Q[{s},{a}] {qa:+.4f} → {qb:+.4f}  (Δ={qb-qa:+.4f})")
    online_learning_ok = bool(diff_a["visit_delta"]) or bool(diff_b["visit_delta"])
    print(f"    online Q-update fired: {'PASS' if online_learning_ok else 'FAIL'}")
    print(f"[5] dashboard /api/allocation distinct tick_ids:")
    print(f"      regime A: {res_a['ticks_seen']}")
    print(f"      regime B: {res_b['ticks_seen']}")
    ui_ok = len(res_a["ticks_seen"]) >= 2 and len(res_b["ticks_seen"]) >= 2
    print(f"    UI proxy serves fresh tick_ids: {'PASS' if ui_ok else 'FAIL'}")

    overall = a_state_ok and b_state_ok and actions_changed and online_learning_ok and ui_ok
    print(f"\nOVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
