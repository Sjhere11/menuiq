"""Price elasticity from a natural experiment, plus a what-if scenario engine.

Method (difference-in-differences on demand per 100 orders):

For an item whose price changed on date D, compare its units per 100 orders in a
window before and after D, then divide by the same ratio for unchanged items in
the same category. Elasticity = ln(relative demand ratio) / ln(price ratio).
Bootstrapping over days gives a 95% interval.

Single-item estimates are noisy with a ~10% price move over six weeks, so the
module also reports a pooled menu-wide estimate (mean of the item estimates,
bootstrapped jointly), which is what the scenario engine uses.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config as C
from . import db

log = logging.getLogger(__name__)

PRE_DAYS = 42
POST_DAYS = 42


def _daily_units_per_100_orders() -> pd.DataFrame:
    units = db.query("SELECT order_date, item_name, category, units FROM v_item_daily")
    orders = db.query("SELECT order_date, COUNT(*) AS orders FROM fact_orders GROUP BY 1")
    df = units.merge(orders, on="order_date")
    df["u100"] = 100.0 * df["units"] / df["orders"]
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df


def _window_series(df: pd.DataFrame, names: list[str], start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    sub = df[df["item_name"].isin(names) & df["order_date"].between(start, end)]
    return sub.groupby("order_date")["u100"].sum().to_numpy()


def _elasticity(tp: np.ndarray, tq: np.ndarray, cp: np.ndarray, cq: np.ndarray, price_ratio: float) -> float:
    rel = (tq.mean() / tp.mean()) / (cq.mean() / cp.mean())
    return float(np.log(rel) / np.log(price_ratio))


def estimate_elasticities(n_boot: int = 2000, seed: int = C.SEED) -> tuple[pd.DataFrame, dict[str, float]]:
    """Return (per-item estimates, pooled estimate with 95% interval)."""
    rng = np.random.default_rng(seed)
    df = _daily_units_per_100_orders()
    d0 = pd.Timestamp(C.PRICE_CHANGE_DATE)
    pre = (d0 - pd.Timedelta(days=PRE_DAYS), d0 - pd.Timedelta(days=1))
    post = (d0, d0 + pd.Timedelta(days=POST_DAYS - 1))
    items = db.query("SELECT item_name, category, list_price, unit_cost FROM dim_item")
    changed = {pc.item for pc in C.PRICE_CHANGES}

    rows = []
    boot_matrix = []
    for pc in C.PRICE_CHANGES:
        meta = items[items["item_name"] == pc.item].iloc[0]
        controls = items[(items["category"] == meta["category"]) & ~items["item_name"].isin(changed)][
            "item_name"
        ].tolist()
        t_pre = _window_series(df, [pc.item], *pre)
        t_post = _window_series(df, [pc.item], *post)
        c_pre = _window_series(df, controls, *pre)
        c_post = _window_series(df, controls, *post)
        price_ratio = pc.new_price / meta["list_price"]

        point = _elasticity(t_pre, t_post, c_pre, c_post, price_ratio)
        boots = np.array(
            [
                _elasticity(
                    rng.choice(t_pre, len(t_pre)),
                    rng.choice(t_post, len(t_post)),
                    rng.choice(c_pre, len(c_pre)),
                    rng.choice(c_post, len(c_post)),
                    price_ratio,
                )
                for _ in range(n_boot)
            ]
        )
        boot_matrix.append(boots)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        rows.append(
            {
                "item": pc.item,
                "category": meta["category"],
                "old_price": float(meta["list_price"]),
                "new_price": float(pc.new_price),
                "price_change_pct": 100 * (price_ratio - 1),
                "elasticity_est": point,
                "ci_low": float(lo),
                "ci_high": float(hi),
                "ci_width": float(hi - lo),
                "true_elasticity": pc.true_elasticity,
                "true_in_ci": bool(lo <= pc.true_elasticity <= hi),
            }
        )
    out = pd.DataFrame(rows)

    pooled_boots = np.mean(np.vstack(boot_matrix), axis=0)
    p_lo, p_hi = np.percentile(pooled_boots, [2.5, 97.5])
    pooled = {
        "estimate": float(out["elasticity_est"].mean()),
        "ci_low": float(p_lo),
        "ci_high": float(p_hi),
        "true_mean": float(np.mean([pc.true_elasticity for pc in C.PRICE_CHANGES])),
    }
    log.info("pooled elasticity %.2f [%.2f, %.2f]", pooled["estimate"], p_lo, p_hi)
    return out, pooled


def reprice_scenario(classified: pd.DataFrame, elasticity: float, price_rise: float = 0.05) -> pd.DataFrame:
    """Annual profit impact of raising every Plowhorse price by `price_rise`.

    Units move by (1 + price_rise) ** elasticity. Cannibalisation, competitor
    reactions and any customer-perception effects are ignored.
    """
    plow = classified[classified["class"] == "Plowhorse"].copy()
    plow["new_price"] = plow["avg_price"] * (1 + price_rise)
    plow["new_units"] = plow["units"] * (1 + price_rise) ** elasticity
    unit_cost = plow["avg_price"] - plow["cm_per_unit"]
    plow["new_profit"] = plow["new_units"] * (plow["new_price"] - unit_cost)
    plow["profit_change"] = plow["new_profit"] - plow["gross_profit"]
    return plow[
        [
            "item_name",
            "category",
            "avg_price",
            "new_price",
            "units",
            "new_units",
            "gross_profit",
            "new_profit",
            "profit_change",
        ]
    ].reset_index(drop=True)


def breakeven_elasticity(classified: pd.DataFrame, price_rise: float = 0.05) -> float:
    """Most negative elasticity at which the Plowhorse repricing still breaks even."""
    lo, hi = -6.0, 0.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if reprice_scenario(classified, mid, price_rise)["profit_change"].sum() > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2
