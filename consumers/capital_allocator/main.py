"""Capital Allocator RL — online consumer (F3).

Every TICK_SECONDS:
  1. Compute regime features (trailing 8h windows from Binance REST + bridge).
  2. state_idx = regime_features.state_index(...).
  3. Apply capability + safety masks.
  4. UCB1 over unmasked actions, argmax (tiebreak: lower visit count).
  5. Build AllocationEntry per §7.2 (bridge strips optional fields; see report).
  6. POST /allocation.
  7. Pull previous tick's reward from /strategy/tick_pnl?tick_id=<prev> and
     apply Q-update Q[s,a] += ALPHA * (r - Q[s,a]); persist every 10 updates.

Safety rails implemented:
  §5.1 all-negative z-freeze (rolling 24h reward < -2.0 → freeze; > -0.5 → thaw).
  §5.5 dollar drawdown (cum NetPnL < -8% of STARTING_BOOK_USD → freeze +
       DIVERSIFY×0.33 notional).

§5.6 v3 offset: prod cadence → 180s, demo cadence scales linearly so
  offset_demo = round(180 * cadence / 28800). With --allocator-tick-seconds 30
  that yields ~0s, matching the design disclaimer.

CLI example:
  python -m consumers.capital_allocator.main \
    --q-table consumers/capital_allocator/allocator_q.json \
    --allocator-tick-seconds 30 --verbose

Bridge caveat (F6 note): the bridge at line 395 only whitelists
  {tick_id, ts, state_idx, action_idx, action_label, weights, q_values,
   persona_id}. All §7.2 extras (state_label, q_value_second_best,
  exploration_bonus, regime_features, drift_downsize, allocation_frozen,
  frozen_reason, v3_entry_offset_sec, cadence_seconds, next_tick_at,
  pretrained) are DROPPED. This consumer still sends them so a future bridge
  patch can pick them up without producer changes.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import signal as signal_mod
import statistics
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import requests
from dotenv import load_dotenv

# Make `ml/` importable regardless of cwd — the package layout is
#   arc/
#     ml/regime_features.py
#     consumers/capital_allocator/main.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml import regime_features  # noqa: E402

load_dotenv()

log = logging.getLogger("allocator")

# ── Hyperparameters (must mirror §4.5 + pretrain) ─────────────────────────
ALPHA = 0.1
UCB_C = 0.5
NUM_ACTIONS = 7
ACTION_LABELS = [
    "ALL_V1", "ALL_V2", "ALL_V3",
    "KIMCHI_DUAL", "DUAL_FUND", "KIMCHI_FUND", "DIVERSIFY",
]
# (v1, v2, v3) weights, indexed by action_idx — MUST match pretrain.
ACTION_WEIGHTS: list[tuple[float, float, float]] = [
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.5, 0.5, 0.0),
    (0.0, 0.5, 0.5),
    (0.5, 0.0, 0.5),
    (1 / 3, 1 / 3, 1 / 3),
]
DIVERSIFY_IDX = 6
ALL_V3_IDX = 2
V3_ENTRY_OFFSET_PROD_SEC = 180  # §5.6

# Safety rails
Z_FREEZE_LOWER = -2.0
Z_FREEZE_UPPER = -0.5
ROLLING_REWARD_WINDOW_SEC = 24 * 3600
DRAWDOWN_PCT = 0.08  # 8%

# Reward normalization (loaded from allocator_q.json.reward_stats)
DEFAULT_LAMBDA = 0.2
DEFAULT_DOLLAR_SCALE = 0.5

# Binance REST endpoints for vol + funding fallback
BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_PREMIUM_INDEX = "https://fapi.binance.com/fapi/v1/premiumIndex"
TOP10_PERPS = [
    "DOGEUSDT", "XRPUSDT", "SOLUSDT", "ADAUSDT", "TRXUSDT",
    "APTUSDT", "LINKUSDT", "AVAXUSDT", "DOTUSDT", "NEARUSDT",
]

SIGNAL_STALENESS_SEC = 15 * 60  # kimchi/usdc freshness per §3.2


# ── Q-table artifact shape ────────────────────────────────────────────────
@dataclass
class QArtifact:
    q_table: list[list[float]]
    visit_counts: list[list[int]]
    action_weights: list[list[float]]
    reward_stats: dict
    pretrained: bool = True
    state_labels: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "QArtifact":
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            q_table=[list(row) for row in d["q_table"]],
            visit_counts=[list(row) for row in d["visit_counts"]],
            action_weights=[list(row) for row in d.get("action_weights", ACTION_WEIGHTS)],
            reward_stats=d.get("reward_stats", {}),
            pretrained=True,
            state_labels=d.get("state_labels", regime_features.STATE_LABELS),
        )

    def save(self, path: Path) -> None:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        existing["q_table"] = self.q_table
        existing["visit_counts"] = self.visit_counts
        existing["reward_stats"] = self.reward_stats
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Q-table save failed: %s", e)


# ── Feature collector ─────────────────────────────────────────────────────
@dataclass
class FeatureCache:
    vol: Optional[float] = None
    funding_median: Optional[float] = None
    kimchi_premium: Optional[float] = None
    usdc_spread: Optional[float] = None
    vol_ts: float = 0.0
    funding_ts: float = 0.0


class FeatureSource:
    """Pulls regime features with graceful fallback to cached values."""

    def __init__(self, bridge_url: str, session: requests.Session):
        self.bridge_url = bridge_url
        self.session = session
        self.cache = FeatureCache()

    def _binance_vol_8h(self) -> Optional[float]:
        """Trailing 8h realized σ of BTC log returns (minute bars × √480)."""
        try:
            r = self.session.get(
                BINANCE_KLINES,
                params={"symbol": "BTCUSDT", "interval": "1m", "limit": 480},
                timeout=4,
            )
            r.raise_for_status()
            rows = r.json()
            closes = [float(row[4]) for row in rows]
            if len(closes) < 2:
                return None
            rets = []
            for i in range(1, len(closes)):
                if closes[i - 1] > 0 and closes[i] > 0:
                    rets.append(math.log(closes[i] / closes[i - 1]))
            if len(rets) < 30:
                return None
            sd = statistics.pstdev(rets)
            # Scale to 8h σ: minute bars → × √len
            return sd * math.sqrt(len(rets))
        except Exception as e:
            log.warning("binance klines fail: %s", e)
            return None

    def _binance_funding_median(self) -> Optional[float]:
        """Median of top-10 perps' lastFundingRate."""
        try:
            r = self.session.get(BINANCE_PREMIUM_INDEX, timeout=4)
            r.raise_for_status()
            rows = r.json()
            wanted = set(TOP10_PERPS)
            rates = []
            for row in rows:
                sym = row.get("symbol")
                if sym in wanted:
                    try:
                        rates.append(float(row.get("lastFundingRate", 0.0)))
                    except Exception:
                        continue
            if not rates:
                return None
            return statistics.median(rates)
        except Exception as e:
            log.warning("binance premiumIndex fail: %s", e)
            return None

    def _bridge_signal_premium(self, producer_id: str) -> Optional[float]:
        """Latest signal from producer_id: return premium_rate iff fresh."""
        try:
            r = self.session.get(f"{self.bridge_url}/signals/latest", timeout=3)
            r.raise_for_status()
            sigs = r.json().get("signals", [])
            now = time.time()
            # Walk newest to oldest
            for s in reversed(sigs):
                if s.get("producer_id") != producer_id:
                    continue
                ts = float(s.get("timestamp", 0) or 0)
                if ts == 0 or (now - ts) > SIGNAL_STALENESS_SEC:
                    return None  # stale → cold
                try:
                    return abs(float(s.get("premium_rate", 0.0)))
                except Exception:
                    return None
            return None
        except Exception as e:
            log.warning("bridge /signals/latest fail: %s", e)
            return None

    def collect(self) -> tuple[FeatureCache, bool]:
        """Return (features, any_fresh). Caller decides cold routing.

        Resolution order per feature:
          1. FORCE_{VOL,FUNDING,KIMCHI,USDC} env var (verification harness / §12 flip)
          2. ml/regime_override.json file (demo regime injector — see demo/regime_injector.py)
          3. Live REST / bridge signal
        """
        # 1. env override hooks
        def _env_override(name: str) -> tuple[bool, Optional[float]]:
            raw = os.environ.get(f"FORCE_{name}")
            if raw is None:
                return False, None
            if raw.lower() in ("none", "null", ""):
                return True, None
            try:
                return True, float(raw)
            except ValueError:
                return False, None

        # 2. file override — re-read each tick so a rotating injector can live-swap
        override_path = os.environ.get(
            "ARC_REGIME_OVERRIDE",
            str(_REPO_ROOT / "ml" / "regime_override.json"),
        )
        file_override: dict = {}
        try:
            p = Path(override_path)
            if p.exists():
                file_override = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log.debug("regime_override read fail: %s", e)

        def _file_override(key: str) -> tuple[bool, Optional[float]]:
            if key not in file_override:
                return False, None
            v = file_override[key]
            if v is None or (isinstance(v, str) and v.lower() in ("none", "null", "")):
                return True, None
            try:
                return True, float(v)
            except (TypeError, ValueError):
                return False, None

        def _resolve(env_name: str, file_key: str, real: Optional[float]) -> Optional[float]:
            got, v = _env_override(env_name)
            if got:
                return v
            got, v = _file_override(file_key)
            if got:
                return v
            return real

        vol = _resolve("VOL", "vol", self._binance_vol_8h())
        fund = _resolve("FUNDING", "funding_median", self._binance_funding_median())
        kimchi = _resolve("KIMCHI", "kimchi_premium", self._bridge_signal_premium("kimchi_agent"))
        usdc = _resolve("USDC", "usdc_spread", self._bridge_signal_premium("dual_quote_agent"))

        now = time.time()
        if vol is not None:
            self.cache.vol = vol
            self.cache.vol_ts = now
        if fund is not None:
            self.cache.funding_median = fund
            self.cache.funding_ts = now
        # kimchi / usdc are transient: update only when fresh. Staleness already
        # checked inside _bridge_signal_premium (None if stale).
        self.cache.kimchi_premium = kimchi
        self.cache.usdc_spread = usdc
        return self.cache, (vol is not None or fund is not None)


# ── Allocator core ────────────────────────────────────────────────────────
@dataclass
class AllocatorRuntime:
    q: QArtifact
    starting_book_usd: float
    cadence_sec: int
    v3_offset_sec: int
    last_tick_id: Optional[str] = None
    last_state_idx: Optional[int] = None
    last_action_idx: Optional[int] = None
    last_weights: Optional[tuple[float, float, float]] = None
    updates_since_save: int = 0
    rolling_reward: deque = field(default_factory=lambda: deque(maxlen=512))
    boot_time: float = field(default_factory=time.time)
    frozen: bool = False
    frozen_reason: Optional[str] = None
    # Legacy / drift snapshots (not used for gating — stubs for §5.2)
    drift_downsize: dict = field(
        default_factory=lambda: {"v1": 1.0, "v2": 1.0, "v3": 1.0}
    )


def _floor_tick(now: float, cadence: int) -> float:
    return math.floor(now / cadence) * cadence


def _iso_utc(epoch_sec: float) -> str:
    # "2026-04-21T08:00:00Z" — matches §7.2 example
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch_sec))


def apply_capability_mask(funding_bit_hot: bool) -> list[bool]:
    """§2.2 capability: funding_regime cold → mask ALL_V3.
    Returns a length-7 mask, True = allowed."""
    mask = [True] * NUM_ACTIONS
    if not funding_bit_hot:
        mask[ALL_V3_IDX] = False
    return mask


def apply_safety_mask(mask: list[bool]) -> list[bool]:
    """§2.2 safety mask — stub (trailing-72h NetPnL data unavailable). Keep all."""
    return mask[:]


def ucb1_select(
    q_row: list[float],
    n_row: list[int],
    mask: list[bool],
    ucb_c: float,
) -> tuple[int, float, float, list[float]]:
    """Return (chosen_action, best_score, best_bonus, scores[])."""
    total = sum(n_row) + 1
    log_t = math.log(total)
    scores = [-math.inf] * NUM_ACTIONS
    bonuses = [0.0] * NUM_ACTIONS
    for a in range(NUM_ACTIONS):
        if not mask[a]:
            continue
        bonus = ucb_c * math.sqrt(log_t / (n_row[a] + 1))
        scores[a] = q_row[a] + bonus
        bonuses[a] = bonus
    # pick max score; tiebreak on lower visit count (exploration-friendly)
    best_a = -1
    best_score = -math.inf
    for a in range(NUM_ACTIONS):
        if scores[a] == -math.inf:
            continue
        if (
            best_a == -1
            or scores[a] > best_score + 1e-12
            or (
                abs(scores[a] - best_score) <= 1e-12
                and n_row[a] < n_row[best_a]
            )
        ):
            best_a = a
            best_score = scores[a]
    if best_a == -1:  # §5.4 — fully degenerate mask
        best_a = DIVERSIFY_IDX
        best_score = q_row[DIVERSIFY_IDX]
        bonuses[DIVERSIFY_IDX] = 0.0
    return best_a, best_score, bonuses[best_a], scores


def second_best(scores: list[float], winner: int) -> float:
    best = -math.inf
    for a, s in enumerate(scores):
        if a == winner or s == -math.inf:
            continue
        if s > best:
            best = s
    return best if best != -math.inf else 0.0


# ── Reward pulling + Q-update ─────────────────────────────────────────────
def fetch_tick_pnl(
    bridge_url: str, session: requests.Session, tick_id: str
) -> Optional[dict]:
    """GET /strategy/tick_pnl?tick_id=... → {v1: entry, v2: entry, v3: entry}
    or None if incomplete."""
    try:
        r = session.get(
            f"{bridge_url}/strategy/tick_pnl",
            params={"tick_id": tick_id},
            timeout=3,
        )
        r.raise_for_status()
        body = r.json()
        if not body.get("complete"):
            return None
        return body.get("entries", {})
    except Exception as e:
        log.warning("tick_pnl fetch fail: %s", e)
        return None


def compute_reward(
    weights: tuple[float, float, float],
    entries: dict,
    stats: dict,
) -> Optional[float]:
    """§3.2 z-score + dollar tiebreaker. Returns None if any strategy missing."""
    try:
        pnls = {s: float(entries[s]["realized_pnl_usd"]) for s in ("v1", "v2", "v3")}
    except (KeyError, TypeError, ValueError):
        return None
    mu = {s: float(stats.get(f"mu_{s}", 0.0)) for s in ("v1", "v2", "v3")}
    sig = {s: max(float(stats.get(f"sigma_{s}", 1.0)), 1e-6) for s in ("v1", "v2", "v3")}
    w = {"v1": weights[0], "v2": weights[1], "v3": weights[2]}
    z = sum(w[s] * (pnls[s] - mu[s]) / sig[s] for s in ("v1", "v2", "v3"))
    dollar_scale = max(float(stats.get("dollar_scale", DEFAULT_DOLLAR_SCALE)), 1e-6)
    dollar = sum(w[s] * pnls[s] for s in ("v1", "v2", "v3")) / dollar_scale
    lam = float(stats.get("lambda", DEFAULT_LAMBDA))
    return (1 - lam) * z + lam * dollar


# ── Safety rail helpers ───────────────────────────────────────────────────
def prune_rolling(rt: AllocatorRuntime, now: float) -> None:
    cutoff = now - ROLLING_REWARD_WINDOW_SEC
    while rt.rolling_reward and rt.rolling_reward[0][0] < cutoff:
        rt.rolling_reward.popleft()


def rolling_sum(rt: AllocatorRuntime) -> float:
    return sum(r for _, r in rt.rolling_reward)


def fetch_drawdown_pnl(bridge_url: str, session: requests.Session) -> Optional[float]:
    """§5.5 — cumulative NetPnL proxy: bridge /economics/summary.strategy_pnl_90m sum.
    Returns None if unavailable (skip rail check)."""
    try:
        r = session.get(f"{bridge_url}/economics/summary", timeout=3)
        r.raise_for_status()
        body = r.json()
        spn = body.get("strategy_pnl_90m", {}) or {}
        return float(spn.get("v1", 0)) + float(spn.get("v2", 0)) + float(spn.get("v3", 0))
    except Exception:
        return None


def evaluate_safety(rt: AllocatorRuntime, bridge_url: str, session: requests.Session) -> None:
    """Update rt.frozen / rt.frozen_reason per §5.1 + §5.5. No-op if rails silent."""
    now = time.time()
    prune_rolling(rt, now)
    rsum = rolling_sum(rt)

    # §5.1 z-freeze
    if rt.frozen_reason == "Z_ROLLING":
        if rsum > Z_FREEZE_UPPER:
            log.info("§5.1 z-freeze UNFREEZE (rolling=%.3f > %.2f)", rsum, Z_FREEZE_UPPER)
            rt.frozen = False
            rt.frozen_reason = None
    else:
        if rsum < Z_FREEZE_LOWER and len(rt.rolling_reward) >= 3:
            log.warning("§5.1 z-freeze FIRE (rolling=%.3f < %.2f)", rsum, Z_FREEZE_LOWER)
            rt.frozen = True
            rt.frozen_reason = "Z_ROLLING"

    # §5.5 dollar drawdown — distinct rail; freeze overrides z
    dd = fetch_drawdown_pnl(bridge_url, session)
    if dd is not None:
        threshold = -DRAWDOWN_PCT * rt.starting_book_usd
        if dd < threshold and rt.frozen_reason != "DRAWDOWN_RAIL":
            log.warning(
                "§5.5 DRAWDOWN_RAIL FIRE (cum=$%.3f < threshold $%.3f)",
                dd, threshold,
            )
            rt.frozen = True
            rt.frozen_reason = "DRAWDOWN_RAIL"
        # Drawdown rail "requires manual unfreeze" per design — no auto-thaw.


# ── Publish + main loop ───────────────────────────────────────────────────
def build_payload(
    rt: AllocatorRuntime,
    tick_epoch: float,
    state_idx: int,
    action_idx: int,
    ucb_bonus: float,
    scores: list[float],
    features: FeatureCache,
    notional_scalar: float,
) -> dict:
    w_raw = ACTION_WEIGHTS[action_idx]
    w = {"v1": w_raw[0], "v2": w_raw[1], "v3": w_raw[2]}
    q_row = rt.q.q_table[state_idx]
    q_winner = q_row[action_idx]
    payload = {
        "tick_id": _iso_utc(tick_epoch),
        "ts": _iso_utc(tick_epoch),
        "state_idx": state_idx,
        "action_idx": action_idx,
        "action_label": ACTION_LABELS[action_idx],
        "weights": w,
        "q_values": list(q_row),
        # — §7.2 extras (bridge strips these; see module docstring) —
        "state_label": rt.q.state_labels[state_idx] if state_idx < len(rt.q.state_labels) else regime_features.describe(state_idx),
        "q_value": q_winner,
        "q_value_second_best": second_best(scores, action_idx),
        "exploration_bonus": ucb_bonus,
        "ucb_score": q_winner + ucb_bonus,
        "regime_features": {
            "vol": features.vol,
            "funding_median": features.funding_median,
            "kimchi_premium": features.kimchi_premium,
            "usdc_spread": features.usdc_spread,
        },
        "drift_downsize": rt.drift_downsize,
        "allocation_frozen": rt.frozen,
        "frozen_reason": rt.frozen_reason,
        "v3_entry_offset_sec": rt.v3_offset_sec if w["v3"] > 0 else 0,
        "cadence_seconds": rt.cadence_sec,
        "next_tick_at": int(tick_epoch + rt.cadence_sec),
        "pretrained": rt.q.pretrained,
        "notional_scalar": notional_scalar,
    }
    return payload


def publish_allocation(
    bridge_url: str, session: requests.Session, payload: dict
) -> bool:
    try:
        r = session.post(f"{bridge_url}/allocation", json=payload, timeout=4)
        if r.status_code == 200:
            return True
        log.warning("bridge /allocation %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("POST /allocation fail: %s", e)
    return False


def tick(
    rt: AllocatorRuntime,
    fsrc: FeatureSource,
    bridge_url: str,
    session: requests.Session,
    q_path: Optional[Path],
    persist_every: int,
    persist: bool,
    verbose: bool,
) -> None:
    now = time.time()
    tick_epoch = _floor_tick(now, rt.cadence_sec)
    tick_id = _iso_utc(tick_epoch)

    # 1. Online Q-update for PREVIOUS tick (if reward carried)
    if rt.last_tick_id is not None and rt.last_tick_id != tick_id:
        entries = fetch_tick_pnl(bridge_url, session, rt.last_tick_id)
        if entries:
            reward = compute_reward(
                rt.last_weights or (0.0, 0.0, 0.0),
                entries,
                rt.q.reward_stats,
            )
            if reward is not None and rt.last_state_idx is not None and rt.last_action_idx is not None:
                s, a = rt.last_state_idx, rt.last_action_idx
                q_old = rt.q.q_table[s][a]
                rt.q.q_table[s][a] = q_old + ALPHA * (reward - q_old)
                rt.q.visit_counts[s][a] += 1
                rt.rolling_reward.append((now, reward))
                rt.updates_since_save += 1
                log.info(
                    "Q-update s=%d a=%s r=%+.3f Q %.3f→%.3f n=%d",
                    s, ACTION_LABELS[a], reward, q_old,
                    rt.q.q_table[s][a], rt.q.visit_counts[s][a],
                )
                if persist and q_path is not None and rt.updates_since_save >= persist_every:
                    rt.q.save(q_path)
                    rt.updates_since_save = 0
        elif verbose:
            log.info("no reward yet for prev tick_id=%s", rt.last_tick_id)

    # 2. Collect features
    features, any_fresh = fsrc.collect()
    if not any_fresh:
        log.warning("no fresh regime features (Binance REST failed?) — using cached")

    # 3. State index
    state_idx = regime_features.state_index(
        features.vol,
        features.funding_median,
        features.kimchi_premium,
        features.usdc_spread,
    )

    # 4. Safety evaluation (may set rt.frozen)
    evaluate_safety(rt, bridge_url, session)

    # 5. Decide action
    notional_scalar = 1.0
    if rt.frozen:
        action_idx = DIVERSIFY_IDX
        ucb_bonus = 0.0
        scores = list(rt.q.q_table[state_idx])
        if rt.frozen_reason == "DRAWDOWN_RAIL":
            notional_scalar = 0.33
    else:
        funding_hot = (
            features.funding_median is not None
            and features.funding_median >= regime_features.FUNDING_P90
        )
        mask = apply_capability_mask(funding_hot)
        mask = apply_safety_mask(mask)
        action_idx, best_score, ucb_bonus, scores = ucb1_select(
            rt.q.q_table[state_idx],
            rt.q.visit_counts[state_idx],
            mask,
            UCB_C,
        )
        # Cold sentinel → design forces DIVERSIFY
        if state_idx == regime_features.COLD_SENTINEL:
            action_idx = DIVERSIFY_IDX
            ucb_bonus = 0.0

    # 6. Build + publish
    payload = build_payload(
        rt, tick_epoch, state_idx, action_idx,
        ucb_bonus, scores, features, notional_scalar,
    )
    ok = publish_allocation(bridge_url, session, payload)

    if verbose or logging.getLogger().isEnabledFor(logging.DEBUG):
        weights = payload["weights"]
        log.info(
            "tick=%s state=%d(%s) mask=%s action=%d(%s) w=v1:%.2f/v2:%.2f/v3:%.2f "
            "Q=%.3f bonus=%.3f 2nd=%.3f frozen=%s v3_off=%ds notional×%.2f post=%s",
            tick_id, state_idx, payload["state_label"],
            "cap_only" if not rt.frozen else f"FROZEN:{rt.frozen_reason}",
            action_idx, ACTION_LABELS[action_idx],
            weights["v1"], weights["v2"], weights["v3"],
            payload["q_value"], payload["exploration_bonus"],
            payload["q_value_second_best"], rt.frozen,
            payload["v3_entry_offset_sec"], notional_scalar,
            "ok" if ok else "FAIL",
        )
    else:
        log.info(
            "tick=%s state=%d action=%s%s",
            tick_id, state_idx, ACTION_LABELS[action_idx],
            f" [{rt.frozen_reason}]" if rt.frozen else "",
        )

    # 7. Remember for next tick's reward update
    rt.last_tick_id = tick_id
    rt.last_state_idx = state_idx
    rt.last_action_idx = action_idx
    w = ACTION_WEIGHTS[action_idx]
    rt.last_weights = (w[0], w[1], w[2])


def wait_for_bridge(bridge_url: str, session: requests.Session, timeout_sec: int = 30) -> bool:
    """Poll /health until ok or timeout. Matches meta_agent pattern."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            r = session.get(f"{bridge_url}/health", timeout=2)
            if r.status_code == 200 and r.json().get("ok"):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Capital Allocator RL — online consumer (F3)."
    )
    ap.add_argument(
        "--q-table",
        default=str(Path(__file__).parent / "allocator_q.json"),
        help="Path to F5's pretrained Q-table JSON.",
    )
    ap.add_argument(
        "--allocator-tick-seconds",
        type=int,
        default=28800,
        help="Decision cadence; 28800 = 8h prod, 30 for demo.",
    )
    ap.add_argument(
        "--v3-entry-offset-sec",
        type=int,
        default=-1,
        help="Override §5.6 v3 entry offset. -1 = auto-scale from cadence.",
    )
    ap.add_argument(
        "--bridge-url",
        default=os.environ.get("ARC_BRIDGE_URL", "http://localhost:3000"),
    )
    ap.add_argument(
        "--starting-book-usd",
        type=float,
        default=50.0,
        help="§5.5 dollar drawdown base.",
    )
    ap.add_argument(
        "--persist-q", type=int, default=1,
        help="1 = save Q-table every N updates; 0 = ephemeral run.",
    )
    ap.add_argument(
        "--persist-every", type=int, default=10,
        help="Save Q-table after this many online updates (§3.1 step 9).",
    )
    ap.add_argument("--max-ticks", type=int, default=0, help="Stop after N ticks (0 = forever).")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    q_path = Path(args.q_table)
    if not q_path.exists():
        log.error("Q-table %s missing — run scripts/pretrain_allocator_q.py first", q_path)
        return 2
    q = QArtifact.load(q_path)
    log.info(
        "loaded Q-table %s (states=%d actions=%d cadence=%ds pretrained=%s)",
        q_path.name, len(q.q_table), NUM_ACTIONS, args.allocator_tick_seconds, q.pretrained,
    )

    # Auto-scale v3 offset per §5.6
    if args.v3_entry_offset_sec >= 0:
        v3_offset = args.v3_entry_offset_sec
    else:
        # prod cadence → 180s; demo cadences scale linearly (→ 0s at 30s)
        v3_offset = round(V3_ENTRY_OFFSET_PROD_SEC * args.allocator_tick_seconds / 28800)
    log.info("v3 entry offset = %ds (cadence=%ds)", v3_offset, args.allocator_tick_seconds)

    session = requests.Session()
    if not wait_for_bridge(args.bridge_url, session):
        log.error("bridge %s /health never returned ok — aborting", args.bridge_url)
        return 3

    rt = AllocatorRuntime(
        q=q,
        starting_book_usd=args.starting_book_usd,
        cadence_sec=args.allocator_tick_seconds,
        v3_offset_sec=v3_offset,
    )
    fsrc = FeatureSource(args.bridge_url, session)

    stopping = {"flag": False}

    def _shutdown(_signum, _frame):
        stopping["flag"] = True
        log.info("shutdown requested")

    try:
        signal_mod.signal(signal_mod.SIGINT, _shutdown)
        signal_mod.signal(signal_mod.SIGTERM, _shutdown)
    except (ValueError, AttributeError):
        pass  # non-main thread / Windows edge

    ticks_run = 0
    try:
        while not stopping["flag"]:
            loop_start = time.time()
            tick(
                rt, fsrc, args.bridge_url, session,
                q_path if args.persist_q else None,
                args.persist_every,
                bool(args.persist_q),
                args.verbose,
            )
            ticks_run += 1
            if args.max_ticks and ticks_run >= args.max_ticks:
                log.info("max-ticks=%d reached", args.max_ticks)
                break
            # Sleep until next cadence boundary
            elapsed = time.time() - loop_start
            wait = max(0.1, args.allocator_tick_seconds - elapsed)
            # Poll stopping flag in small chunks so SIGINT is prompt
            slept = 0.0
            while slept < wait and not stopping["flag"]:
                time.sleep(min(0.5, wait - slept))
                slept += 0.5
    finally:
        if args.persist_q and rt.updates_since_save:
            rt.q.save(q_path)
        log.info(
            "allocator exit. ticks=%d pending_unsaved_updates=%d",
            ticks_run, rt.updates_since_save,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
