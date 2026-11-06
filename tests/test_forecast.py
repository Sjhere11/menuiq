from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from menuiq import forecast


def _daily(n_days: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2025-01-01", periods=n_days)
    frames = []
    for cat, level in [("A", 100), ("B", 40)]:
        frames.append(pd.DataFrame({"date": dates, "category": cat, "units": rng.poisson(level, n_days)}))
    return pd.concat(frames).sort_values(["category", "date"]).reset_index(drop=True)


@pytest.mark.unit
def test_lag_features_are_shifted_by_horizon():
    df = _daily()
    feat = forecast.build_features(df)
    row = feat[(feat["category"] == "A")].iloc[10]
    target_day = row["date"]
    src = df[(df["category"] == "A") & (df["date"] == target_day - pd.Timedelta(days=forecast.H))]
    assert row["lag_h"] == src["units"].iloc[0]


@pytest.mark.unit
def test_features_do_not_leak_data_newer_than_horizon():
    """Changing any value inside the forecast horizon must not alter that row's features."""
    df = _daily()
    base = forecast.build_features(df)
    day = base["date"].iloc[60]
    tampered = df.copy()
    recent = tampered["date"] > day - pd.Timedelta(days=forecast.H)
    tampered.loc[recent, "units"] = 10_000
    alt = forecast.build_features(tampered)
    cols = ["lag_h", "lag_h7", "lag_h14", "lag_h21", "roll7", "roll28"]
    a = base[(base["date"] == day)].sort_values("category")[cols].to_numpy()
    b = alt[(alt["date"] == day)].sort_values("category")[cols].to_numpy()
    np.testing.assert_array_equal(a, b)


@pytest.mark.unit
def test_walk_forward_returns_metrics_for_all_models():
    feat = forecast.build_features(_daily(200))
    metrics, preds = forecast.walk_forward(feat)
    assert set(metrics["model"]) == {"gbm", "4wk_avg", "seasonal_naive"}
    assert metrics["wape"].between(0, 1).all()
    assert preds["fold"].nunique() == 4
    # Test folds are strictly out of sample and in chronological order.
    first_test_day = preds.groupby("fold")["date"].min()
    assert first_test_day.is_monotonic_increasing
