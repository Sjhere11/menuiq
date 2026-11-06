from __future__ import annotations

import pytest

from menuiq import config as C
from menuiq import db


@pytest.mark.integration
def test_row_counts_and_foreign_keys(short_db, short_tables):
    n_lines = db.query("SELECT COUNT(*) AS n FROM fact_order_items", short_db)["n"][0]
    assert n_lines == len(short_tables["fact_order_items"])
    orphans = db.query(
        "SELECT COUNT(*) AS n FROM fact_order_items l LEFT JOIN fact_orders o USING (order_id) "
        "WHERE o.order_id IS NULL",
        short_db,
    )["n"][0]
    assert orphans == 0


@pytest.mark.integration
def test_view_revenue_matches_fact_table(short_db):
    view = db.query("SELECT SUM(revenue) AS r FROM v_item_daily", short_db)["r"][0]
    fact = db.query("SELECT SUM(qty * unit_price) AS r FROM fact_order_items", short_db)["r"][0]
    assert view == pytest.approx(fact)


@pytest.mark.integration
def test_sql_files_run_and_return_expected_result_sets(short_db):
    kpis = db.run_sql_file(C.SQL_DIR / "01_kpis_and_trends.sql", short_db)
    basket = db.run_sql_file(C.SQL_DIR / "02_basket_and_peak_hours.sql", short_db)
    assert len(kpis) == 2 and len(basket) == 3
    assert set(kpis[1]["category"]) == set(C.SEASONALITY)
    assert kpis[1]["profit_share_pct"].sum() == pytest.approx(100, abs=0.5)
    assert basket[1]["cumulative_pct"].iloc[-1] == pytest.approx(100, abs=0.2)
