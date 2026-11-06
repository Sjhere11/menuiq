"""End-to-end run on a temporary location, validated against planted ground truth.

Because the data is simulated, the true price elasticities and the true
item-companion pairs are known. A sound analysis should recover them.
"""

from __future__ import annotations

import json

import pytest

from menuiq import config as C
from menuiq import pipeline


@pytest.fixture(scope="module")
def summary(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("run")
    saved = (C.DB_PATH, C.REPORTS_DIR, C.FIG_DIR, C.MARTS_DIR)
    C.DB_PATH = tmp / "menuiq.db"
    C.REPORTS_DIR = tmp / "reports"
    C.FIG_DIR = C.REPORTS_DIR / "figures"
    C.MARTS_DIR = tmp / "marts"
    C.REPORTS_DIR.mkdir()
    try:
        yield pipeline.run(), tmp
    finally:
        C.DB_PATH, C.REPORTS_DIR, C.FIG_DIR, C.MARTS_DIR = saved


@pytest.mark.integration
def test_artifacts_are_written(summary):
    _, tmp = summary
    assert (tmp / "reports" / "dashboard.html").stat().st_size > 50_000
    assert len(list((tmp / "reports" / "figures").glob("*.png"))) == 6
    assert len(list((tmp / "marts").glob("*.csv"))) == 7
    assert json.loads((tmp / "reports" / "summary.json").read_text())["orders"] > 50_000


@pytest.mark.integration
def test_pooled_elasticity_interval_contains_planted_truth(summary):
    s, _ = summary
    pooled = s["elasticity_pooled"]
    assert pooled["ci_low"] <= pooled["true_mean"] <= pooled["ci_high"]
    assert pooled["estimate"] < 0  # demand falls when price rises


@pytest.mark.integration
def test_basket_analysis_recovers_planted_companions(summary):
    s, _ = summary
    assert s["pair_validation"]["precision_at_k"] >= 0.8


@pytest.mark.integration
def test_forecast_beats_seasonal_naive_out_of_sample(summary):
    s, _ = summary
    wape = {m["model"]: m["wape"] for m in s["forecast_metrics"]}
    assert wape["gbm"] < wape["seasonal_naive"]


@pytest.mark.integration
def test_every_menu_item_is_classified_once(summary):
    s, _ = summary
    assert sum(s["class_counts"].values()) == len(C.MENU)
