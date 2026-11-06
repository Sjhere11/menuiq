from __future__ import annotations

import pandas as pd
import pytest

from menuiq import menu_engineering as me


def _summary() -> pd.DataFrame:
    # Four items, equal-ish popularity bands, designed to hit each class.
    return pd.DataFrame(
        {
            "item_id": [1, 2, 3, 4],
            "item_name": ["star", "plow", "puzzle", "dog"],
            "category": ["x"] * 4,
            "units": [400, 400, 40, 40],
            "revenue": [400 * 100, 400 * 50, 40 * 120, 40 * 50],
            "gross_profit": [400 * 80, 400 * 20, 40 * 90, 40 * 10],
        }
    )


@pytest.mark.unit
def test_each_class_is_assigned_correctly():
    out = me.classify(_summary()).set_index("item_name")
    assert out.loc["star", "class"] == "Star"
    assert out.loc["plow", "class"] == "Plowhorse"
    assert out.loc["puzzle", "class"] == "Puzzle"
    assert out.loc["dog", "class"] == "Dog"


@pytest.mark.unit
def test_thresholds_match_definition():
    out = me.classify(_summary())
    assert out.attrs["pop_threshold"] == pytest.approx(0.7 / 4)
    expected_cm = (400 * 80 + 400 * 20 + 40 * 90 + 40 * 10) / 880
    assert out.attrs["cm_threshold"] == pytest.approx(expected_cm)


@pytest.mark.unit
def test_unit_shares_sum_to_one_and_every_class_has_an_action():
    out = me.classify(_summary())
    assert out["unit_share"].sum() == pytest.approx(1.0)
    assert out["action"].notna().all()
