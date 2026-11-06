from __future__ import annotations

import pandas as pd
import pytest

from menuiq import config as C
from menuiq import generate


@pytest.mark.unit
def test_item_table_is_consistent():
    items = generate.build_item_table()
    assert items["item_id"].is_unique and items["item_name"].is_unique
    assert (items["unit_cost"] < items["list_price"]).all()
    assert set(items["category"]) == set(C.SEASONALITY)


@pytest.mark.unit
def test_every_companion_exists_on_the_menu():
    names = {m[0] for m in C.MENU}
    for first, comps in C.COMPANIONS.items():
        assert first in names
        assert set(comps) <= names


@pytest.mark.integration
def test_generation_is_deterministic(short_tables):
    original = (C.START_DATE, C.END_DATE)
    C.START_DATE, C.END_DATE = "2025-06-25", "2025-07-05"
    try:
        again = generate.generate(seed=7)
    finally:
        C.START_DATE, C.END_DATE = original
    pd.testing.assert_frame_equal(short_tables["fact_order_items"], again["fact_order_items"])


@pytest.mark.integration
def test_fact_tables_are_valid(short_tables):
    orders, lines = short_tables["fact_orders"], short_tables["fact_order_items"]
    assert orders["order_id"].is_unique
    assert set(lines["order_id"]) <= set(orders["order_id"])
    assert (lines["qty"] > 0).all()
    assert (lines["unit_cost"] < lines["unit_price"]).all()
    assert orders["order_hour"].between(8, 21).all()
    assert not lines.duplicated(["order_id", "item_id"]).any()


@pytest.mark.integration
def test_price_change_applies_only_from_change_date(short_tables):
    orders, lines = short_tables["fact_orders"], short_tables["fact_order_items"]
    items = short_tables["dim_item"].set_index("item_name")
    merged = lines.merge(orders[["order_id", "order_date"]], on="order_id")
    cappuccino = items.loc["Cappuccino", "item_id"]
    sub = merged[merged["item_id"] == cappuccino]
    before = sub[sub["order_date"] < pd.Timestamp(C.PRICE_CHANGE_DATE)]["unit_price"]
    after = sub[sub["order_date"] >= pd.Timestamp(C.PRICE_CHANGE_DATE)]["unit_price"]
    new_price = next(pc.new_price for pc in C.PRICE_CHANGES if pc.item == "Cappuccino")
    assert (before == 140).all() and (after == new_price).all()
