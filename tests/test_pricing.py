from __future__ import annotations

import pandas as pd
import pytest

from menuiq import pricing


def _classified() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "item_name": ["a", "b"],
            "category": ["x", "x"],
            "class": ["Plowhorse", "Star"],
            "units": [1000.0, 500.0],
            "avg_price": [40.0, 100.0],
            "cm_per_unit": [30.0, 80.0],
            "gross_profit": [30000.0, 40000.0],
        }
    )


@pytest.mark.unit
def test_only_plowhorses_are_repriced():
    out = pricing.reprice_scenario(_classified(), -1.0, 0.05)
    assert out["item_name"].tolist() == ["a"]


@pytest.mark.unit
def test_zero_elasticity_gains_the_full_price_rise():
    out = pricing.reprice_scenario(_classified(), 0.0, 0.05)
    assert out["profit_change"].iloc[0] == pytest.approx(1000 * 40 * 0.05)


@pytest.mark.unit
def test_unit_elastic_case_matches_hand_calculation():
    out = pricing.reprice_scenario(_classified(), -1.0, 0.05)
    new_units = 1000 / 1.05
    expected = new_units * (42.0 - 10.0) - 30000
    assert out["profit_change"].iloc[0] == pytest.approx(expected)


@pytest.mark.unit
def test_breakeven_elasticity_gives_zero_profit_change():
    e = pricing.breakeven_elasticity(_classified(), 0.05)
    assert pricing.reprice_scenario(_classified(), e, 0.05)["profit_change"].sum() == pytest.approx(0, abs=1)
    assert pricing.reprice_scenario(_classified(), e + 0.3, 0.05)["profit_change"].sum() > 0
    assert pricing.reprice_scenario(_classified(), e - 0.3, 0.05)["profit_change"].sum() < 0
