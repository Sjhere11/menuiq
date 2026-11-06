"""Market-basket analysis: support, confidence and lift for item pairs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import db


def basket_matrix() -> pd.DataFrame:
    """Boolean order x item matrix (rows = orders, columns = item names)."""
    lines = db.query(
        """
        SELECT l.order_id, i.item_name
        FROM fact_order_items l JOIN dim_item i USING (item_id)
        """
    )
    return pd.crosstab(lines["order_id"], lines["item_name"]).clip(upper=1).astype(bool)


def planted_pair_recall(pairs: pd.DataFrame, top_k: int = 10) -> dict[str, float]:
    """Validation against ground truth: how many top-lift pairs are planted companions?"""
    from . import config as C  # local import keeps module dependencies minimal

    planted = {frozenset((a, b)) for a, comp in C.COMPANIONS.items() for b in comp}
    top = pairs.head(top_k)
    hits = sum(frozenset((r.item_a, r.item_b)) in planted for r in top.itertuples())
    return {"top_k": float(top_k), "planted_hits": float(hits), "precision_at_k": hits / top_k}


def pair_rules(basket: pd.DataFrame, min_support: float = 0.005) -> pd.DataFrame:
    """All item pairs with support >= min_support, with confidence and lift."""
    x = basket.to_numpy(dtype=np.int32)
    n_orders = x.shape[0]
    co = x.T @ x
    single = np.diag(co).astype(float)
    names = basket.columns.to_numpy()
    rows = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            together = co[i, j]
            support = together / n_orders
            if support < min_support:
                continue
            p_i, p_j = single[i] / n_orders, single[j] / n_orders
            rows.append(
                {
                    "item_a": names[i],
                    "item_b": names[j],
                    "orders_together": int(together),
                    "support": support,
                    "confidence_a_to_b": together / single[i],
                    "confidence_b_to_a": together / single[j],
                    "lift": support / (p_i * p_j),
                }
            )
    columns = [
        "item_a",
        "item_b",
        "orders_together",
        "support",
        "confidence_a_to_b",
        "confidence_b_to_a",
        "lift",
    ]
    out = pd.DataFrame(rows, columns=columns)
    return out.sort_values("lift", ascending=False).reset_index(drop=True)
