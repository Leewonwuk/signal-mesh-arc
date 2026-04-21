"""
Regime GBM — sklearn Gradient Boosting classifier trained on v1.3 parquet data.

Input : 1s backtest data (87 pairs × 20260419, in `data/backtest/1s/`)
Output: joblib-saved model at `ml/regime_gbm.joblib`

Feature engineering
-------------------
From the joined USDT/USDC quote stream we compute the premium rate:
    premium_t = (mid_usdc_t - mid_usdt_t) / mid_usdt_t

Rolling features over windows W = [10s, 30s, 120s]:
    - mean, std, zscore of premium
    - slope (linear fit) as momentum proxy
    - sign-flip count (proxy for microstructure noise)

Label (regime)
--------------
Using forward 30s return of the premium:
    fwd_max  = premium[t+1 : t+30].max()
    fwd_min  = premium[t+1 : t+30].min()
    fwd_end  = premium[t+30]

    trending    — |fwd_end - premium_t| > 2σ_30s    (persistent drift)
    mean_revert — premium_t crosses zero within 30s
    event       — |premium_t| > 3σ_300s             (outlier spike)
    noise       — otherwise

Downstream use
--------------
    from ml.regime_gbm import RegimeModel
    m = RegimeModel.load()
    label = m.predict_single(premium_now, premium_window)

Run:
    python -m ml.regime_gbm --out ml/regime_gbm.joblib
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


log = logging.getLogger("regime_gbm")


_REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "v1_3_replay"
_LEGACY_PRIVATE_DIR = Path(
    r"C:\Users\user\trading\arb\ai_agent_trading_v1.0\v2_dual_quote_arb\data\backtest\1s"
)
DEFAULT_DATA_DIR = Path(
    os.environ.get(
        "ARC_DEMO_DATA_DIR",
        str(_REPO_DATA_DIR if _REPO_DATA_DIR.exists() else _LEGACY_PRIVATE_DIR),
    )
)
WINDOWS = (10, 30, 120)
FWD_WINDOW = 30
EVENT_LOOKBACK = 300


def _pair_list(data_dir: Path, date: str) -> list[str]:
    usdt = {p.stem.replace(f"USDT_{date}", "") for p in data_dir.glob(f"*USDT_{date}.parquet")}
    usdc = {p.stem.replace(f"USDC_{date}", "") for p in data_dir.glob(f"*USDC_{date}.parquet")}
    return sorted(usdt & usdc)


def _load_premium(data_dir: Path, symbol: str, date: str) -> pd.Series:
    ut = pd.read_parquet(data_dir / f"{symbol}USDT_{date}.parquet")
    uc = pd.read_parquet(data_dir / f"{symbol}USDC_{date}.parquet")

    def _mid(df: pd.DataFrame) -> pd.Series:
        if "bid" in df and "ask" in df:
            return (df["bid"] + df["ask"]) / 2.0
        if "mid" in df:
            return df["mid"]
        if "close" in df:
            return df["close"]
        raise KeyError(f"no mid/bid/ask/close for {symbol}")

    ut = ut.assign(mid=_mid(ut))[["timestamp", "mid"]].rename(columns={"mid": "mid_usdt"})
    uc = uc.assign(mid=_mid(uc))[["timestamp", "mid"]].rename(columns={"mid": "mid_usdc"})
    df = ut.merge(uc, on="timestamp", how="inner").sort_values("timestamp")
    df["premium"] = (df["mid_usdc"] - df["mid_usdt"]) / df["mid_usdt"]
    return df.set_index("timestamp")["premium"]


def _features(premium: pd.Series) -> pd.DataFrame:
    out: dict[str, pd.Series] = {"premium": premium}
    for w in WINDOWS:
        roll = premium.rolling(w, min_periods=max(2, w // 2))
        mean = roll.mean()
        std = roll.std().replace(0, np.nan)
        out[f"mean_{w}"] = mean
        out[f"std_{w}"] = std.fillna(0)
        out[f"z_{w}"] = ((premium - mean) / std).fillna(0)
        # slope via simple diff mean (cheaper than polyfit)
        out[f"slope_{w}"] = premium.diff().rolling(w).mean().fillna(0)
        sign_flip = (np.sign(premium.diff()).diff().abs() > 0).astype(int)
        out[f"flips_{w}"] = sign_flip.rolling(w).sum().fillna(0)
    return pd.DataFrame(out).dropna()


def _labels(premium: pd.Series) -> pd.Series:
    """Regime labels from forward 30s behavior.

    Fix (Karpathy review 2026-04-21): the previous version thresholded
    *forward* drift by *forward* std, which is a tautology — any row whose
    forward window had drift > 2× its own std got tagged "trending." Now we
    normalize by *causal* long-window volatility so the label carries real
    information about whether the move was predictable from the present.
    """
    sigma_long = premium.rolling(EVENT_LOOKBACK, min_periods=30).std()
    fwd_end = premium.shift(-FWD_WINDOW)

    # Vectorized zero-cross detection in forward window
    sign_now = np.sign(premium)
    fwd_sign_min = np.sign(premium).rolling(FWD_WINDOW).min().shift(-FWD_WINDOW)
    fwd_sign_max = np.sign(premium).rolling(FWD_WINDOW).max().shift(-FWD_WINDOW)
    crossed = (sign_now * fwd_sign_min < 0) | (sign_now * fwd_sign_max < 0)

    drift = (fwd_end - premium).abs()
    is_event = premium.abs() > 3 * sigma_long
    is_trend = drift > 2 * sigma_long        # causal normalization
    is_revert = crossed

    label = pd.Series("noise", index=premium.index)
    label[is_revert] = "mean_revert"
    label[is_trend] = "trending"
    label[is_event] = "event"  # event supersedes (rare, highest value)
    return label


@dataclass
class RegimeModel:
    model: object  # sklearn GradientBoostingClassifier
    feature_cols: list[str]
    classes: list[str]

    def predict_single(self, window: list[float]) -> tuple[str, float]:
        """Given the last ~120s of premium values, return (label, confidence)."""
        s = pd.Series(window)
        feats = _features(s).iloc[-1:]
        feats = feats[self.feature_cols]
        probs = self.model.predict_proba(feats.values)[0]
        idx = int(np.argmax(probs))
        return self.classes[idx], float(probs[idx])

    def save(self, path: Path) -> None:
        import joblib
        joblib.dump(
            {"model": self.model, "feature_cols": self.feature_cols, "classes": self.classes},
            path,
        )

    @classmethod
    def load(cls, path: Path | str = "ml/regime_gbm.joblib") -> "RegimeModel":
        import joblib
        d = joblib.load(path)
        return cls(model=d["model"], feature_cols=d["feature_cols"], classes=list(d["classes"]))


def train(data_dir: Path, date: str, out: Path, max_symbols: int | None = None) -> RegimeModel:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

    symbols = _pair_list(data_dir, date)
    if max_symbols:
        symbols = symbols[:max_symbols]
    log.info("Training regime GBM on %d pairs (%s)", len(symbols), date)

    feats_all, labels_all = [], []
    for sym in symbols:
        try:
            prem = _load_premium(data_dir, sym, date)
        except Exception as e:
            log.warning("skip %s: %s", sym, e)
            continue
        if len(prem) < EVENT_LOOKBACK + FWD_WINDOW:
            continue
        feats = _features(prem)
        labs = _labels(prem).reindex(feats.index).dropna()
        feats = feats.loc[labs.index]
        feats_all.append(feats)
        labels_all.append(labs)

    if not feats_all:
        raise RuntimeError("no training data built")

    X = pd.concat(feats_all)
    y = pd.concat(labels_all)
    log.info("dataset: %d rows, label dist:\n%s", len(X), y.value_counts().to_string())

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    clf = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.08, random_state=42
    )
    clf.fit(X_tr.values, y_tr.values)

    preds = clf.predict(X_te.values)
    log.info("holdout report:\n%s", classification_report(y_te, preds))

    model = RegimeModel(
        model=clf, feature_cols=list(X.columns), classes=list(clf.classes_)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    log.info("saved → %s", out)
    return model


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--date", default="20260419")
    ap.add_argument("--out", type=Path, default=Path("ml/regime_gbm.joblib"))
    ap.add_argument("--max-symbols", type=int, default=None)
    args = ap.parse_args()
    try:
        train(args.data_dir, args.date, args.out, args.max_symbols)
    except Exception as e:
        log.error("train failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
