"""Menu engineering (Kasavana-Smith matrix) on realised sales.

Each item is placed in one of four classes using two thresholds:

* Popularity: unit share >= 70% of an equal share (1 / n_items).
* Profitability: contribution margin per unit >= the sales-weighted average
  contribution margin per unit across the whole menu.
"""

from __future__ import annotations

import pandas as pd

from . import db

POPULARITY_FACTOR = 0.70

ACTIONS = {
    "Star": "Protect quality, feature on the menu, do not discount.",
    "Plowhorse": "Popular but thin margin: test a small price rise or cut portion/ingredient cost.",
    "Puzzle": "High margin but under-ordered: reposition on the menu, train staff to suggest, bundle.",
    "Dog": "Low sales and low margin: rework the recipe or retire the item.",
}


def item_summary() -> pd.DataFrame:
    sql = """
        SELECT item_id, item_name, category,
               SUM(units)        AS units,
               SUM(revenue)      AS revenue,
               SUM(gross_profit) AS gross_profit
        FROM v_item_daily
        GROUP BY item_id, item_name, category
    """
    return db.query(sql)


def classify(summary: pd.DataFrame, popularity_factor: float = POPULARITY_FACTOR) -> pd.DataFrame:
    """Return the summary with unit share, CM/unit, thresholds and a class label."""
    df = summary.copy()
    n_items = len(df)
    total_units = df["units"].sum()
    df["unit_share"] = df["units"] / total_units
    df["avg_price"] = df["revenue"] / df["units"]
    df["cm_per_unit"] = df["gross_profit"] / df["units"]
    df["margin_pct"] = 100 * df["gross_profit"] / df["revenue"]

    pop_threshold = popularity_factor * (1.0 / n_items)
    cm_threshold = df["gross_profit"].sum() / total_units  # weighted average CM / unit

    df["high_popularity"] = df["unit_share"] >= pop_threshold
    df["high_cm"] = df["cm_per_unit"] >= cm_threshold

    def label(row: pd.Series) -> str:
        if row["high_popularity"] and row["high_cm"]:
            return "Star"
        if row["high_popularity"]:
            return "Plowhorse"
        if row["high_cm"]:
            return "Puzzle"
        return "Dog"

    df["class"] = df.apply(label, axis=1)
    df["action"] = df["class"].map(ACTIONS)
    df.attrs["pop_threshold"] = pop_threshold
    df.attrs["cm_threshold"] = cm_threshold
    return df.sort_values("gross_profit", ascending=False).reset_index(drop=True)
