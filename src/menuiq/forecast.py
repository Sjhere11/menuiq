"""7-day-ahead demand forecasting by category with leakage-safe features.

Every feature for target date t is built from data on or before t - HORIZON, so
the model could really have been run a week earlier. Evaluation is expanding-window
walk-forward (refit per fold) and compares against two honest baselines.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from . import config as C
from . import db

log = logging.getLogger(__name__)

H = C.FORECAST_HORIZON_DAYS
FEATURES = [
    "lag_h",
    "lag_h7",
    "lag_h14",
    "lag_h21",
    "roll7",
    "roll28",
    "dow",
    "is_event",
    "cat_code",
]


def category_daily() -> pd.DataFrame:
    df = db.query("SELECT order_date AS date, category, SUM(units) AS units FROM v_item_daily GROUP BY 1, 2")
    df["date"] = pd.to_datetime(df["date"])
    full = pd.MultiIndex.from_product(
        [pd.date_range(df["date"].min(), df["date"].max()), sorted(df["category"].unique())],
        names=["date", "category"],
    )
    df = df.set_index(["date", "category"]).reindex(full, fill_value=0).reset_index()
    return df.sort_values(["category", "date"]).reset_index(drop=True)


def build_features(df: pd.DataFrame, horizon: int = H) -> pd.DataFrame:
    out = df.copy()
    g = out.groupby("category")["units"]
    out["lag_h"] = g.shift(horizon)
    out["lag_h7"] = g.shift(horizon + 7)
    out["lag_h14"] = g.shift(horizon + 14)
    out["lag_h21"] = g.shift(horizon + 21)
    shifted = g.shift(horizon)
    out["roll7"] = shifted.groupby(out["category"]).transform(lambda s: s.rolling(7).mean())
    out["roll28"] = shifted.groupby(out["category"]).transform(lambda s: s.rolling(28).mean())
    out["dow"] = out["date"].dt.dayofweek
    events = {pd.Timestamp(d) for d in C.EVENT_DAYS}
    out["is_event"] = out["date"].isin(events).astype(int)
    out["cat_code"] = out["category"].astype("category").cat.codes
    return out.dropna(subset=["lag_h21", "roll28"]).reset_index(drop=True)


def _wape(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.abs(actual - pred).sum() / actual.sum())


def walk_forward(feat: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (metrics per model, predictions on all test rows)."""
    last = feat["date"].max()
    preds = []
    for k in range(C.CV_FOLDS):
        test_end = last - pd.Timedelta(days=(C.CV_FOLDS - 1 - k) * C.CV_FOLD_DAYS)
        test_start = test_end - pd.Timedelta(days=C.CV_FOLD_DAYS - 1)
        train = feat[feat["date"] < test_start]
        test = feat[feat["date"].between(test_start, test_end)].copy()

        # Scale target per category so one model serves all categories.
        scale = train.groupby("category")["units"].mean()
        y_train = train["units"] / train["category"].map(scale)
        model = HistGradientBoostingRegressor(
            max_iter=250,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=15,
            l2_regularization=1.0,
            random_state=C.SEED,
        )
        x_train = train[FEATURES].assign(
            **{
                c: train[c] / train["category"].map(scale)
                for c in ["lag_h", "lag_h7", "lag_h14", "lag_h21", "roll7", "roll28"]
            }
        )
        model.fit(x_train, y_train)
        x_test = test[FEATURES].assign(
            **{
                c: test[c] / test["category"].map(scale)
                for c in ["lag_h", "lag_h7", "lag_h14", "lag_h21", "roll7", "roll28"]
            }
        )
        test["pred_gbm"] = model.predict(x_test) * test["category"].map(scale)
        test["pred_seasonal_naive"] = test["lag_h"] if H == 7 else test["lag_h7"]
        test["pred_4wk_avg"] = test[["lag_h", "lag_h7", "lag_h14", "lag_h21"]].mean(axis=1)
        test["fold"] = k + 1
        preds.append(test)
    allp = pd.concat(preds, ignore_index=True)

    rows = []
    for name in ["pred_seasonal_naive", "pred_4wk_avg", "pred_gbm"]:
        a, p = allp["units"].to_numpy(float), allp[name].to_numpy(float)
        fold_wape = [
            _wape(f["units"].to_numpy(float), f[name].to_numpy(float)) for _, f in allp.groupby("fold")
        ]
        rows.append(
            {
                "model": name.replace("pred_", ""),
                "wape": _wape(a, p),
                "mae_units": float(np.abs(a - p).mean()),
                "wape_fold_min": min(fold_wape),
                "wape_fold_max": max(fold_wape),
            }
        )
    metrics = pd.DataFrame(rows).sort_values("wape").reset_index(drop=True)
    log.info("best model: %s (WAPE %.3f)", metrics.loc[0, "model"], metrics.loc[0, "wape"])
    return metrics, allp


def per_category_wape(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cat, f in preds.groupby("category"):
        a = f["units"].to_numpy(float)
        rows.append(
            {
                "category": cat,
                "wape_seasonal_naive": _wape(a, f["pred_seasonal_naive"].to_numpy(float)),
                "wape_gbm": _wape(a, f["pred_gbm"].to_numpy(float)),
            }
        )
    return pd.DataFrame(rows)
