"""Simulate a year of POS data for one independent cafe.

The data is SYNTHETIC. It is generated from explicit, documented assumptions
(config.py) so that analysis methods can be validated against known ground
truth, e.g. the price elasticities that are planted in the generator.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config as C

log = logging.getLogger(__name__)


def build_item_table() -> pd.DataFrame:
    rows = [
        {
            "item_id": i + 1,
            "item_name": name,
            "category": cat,
            "list_price": float(price),
            "unit_cost": float(cost),
            "base_weight": float(w),
        }
        for i, (name, cat, price, cost, w) in enumerate(C.MENU)
    ]
    return pd.DataFrame(rows)


def _price_on(item: pd.Series, day: pd.Timestamp) -> float:
    for pc in C.PRICE_CHANGES:
        if pc.item == item["item_name"] and day >= pd.Timestamp(C.PRICE_CHANGE_DATE):
            return float(pc.new_price)
    return float(item["list_price"])


def _item_weights(items: pd.DataFrame, day: pd.Timestamp, hour: int) -> np.ndarray:
    """Relative probability of each item being the first pick at (day, hour)."""
    m = day.month - 1
    w = np.empty(len(items))
    elasticity = {pc.item: pc.true_elasticity for pc in C.PRICE_CHANGES}
    base_price = items.set_index("item_name")["list_price"].to_dict()
    for k, row in enumerate(items.itertuples(index=False)):
        weight = row.base_weight
        if row.item_name in C.ITEM_SEASON_OVERRIDE:
            weight *= C.ITEM_SEASON_OVERRIDE[row.item_name][m]
        else:
            weight *= C.SEASONALITY[row.category][m]
        for hours, mult in C.DAYPART_AFFINITY.get(row.category, []):
            if hour in hours:
                weight *= mult
        if row.item_name in elasticity and day >= pd.Timestamp(C.PRICE_CHANGE_DATE):
            new_p = next(p.new_price for p in C.PRICE_CHANGES if p.item == row.item_name)
            weight *= (new_p / base_price[row.item_name]) ** elasticity[row.item_name]
        w[k] = weight
    return w / w.sum()


def generate(seed: int = C.SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    items = build_item_table()
    names = items["item_name"].tolist()
    name_to_idx = {n: i for i, n in enumerate(names)}
    days = pd.date_range(C.START_DATE, C.END_DATE, freq="D")
    hours = np.array(list(C.HOUR_WEIGHTS.keys()))
    hour_p = np.array(list(C.HOUR_WEIGHTS.values()), dtype=float)
    hour_p /= hour_p.sum()

    orders: list[tuple] = []
    lines: list[tuple] = []
    order_id = 0
    weight_cache: dict[tuple[int, int, bool], np.ndarray] = {}

    for t, day in enumerate(days):
        growth = (1 + C.MONTHLY_GROWTH) ** (t / 30.0)
        mu = (
            C.BASE_DAILY_ORDERS
            * growth
            * C.DOW_FACTOR[day.dayofweek]
            * C.EVENT_DAYS.get(day.strftime("%Y-%m-%d"), 1.0)
        )
        n_orders = max(20, int(rng.poisson(mu * rng.lognormal(0, 0.06))))
        order_hours = rng.choice(hours, size=n_orders, p=hour_p)
        channels = rng.choice(C.CHANNELS, size=n_orders, p=C.CHANNEL_P)
        pays = rng.choice(C.PAYMENTS, size=n_orders, p=C.PAYMENT_P)
        for k in range(n_orders):
            order_id += 1
            h = int(order_hours[k])
            minute = int(rng.integers(0, 60))
            ts = day + pd.Timedelta(hours=h, minutes=minute)
            orders.append((order_id, ts, day.normalize(), h, channels[k], pays[k]))

            key = (day.month, h, day >= pd.Timestamp(C.PRICE_CHANGE_DATE))
            if key not in weight_cache:
                weight_cache[key] = _item_weights(items, day, h)
            p = weight_cache[key]
            first = int(rng.choice(len(items), p=p))
            basket = {first: 1}
            extra = min(3, int(rng.poisson(0.9)))
            for _ in range(extra):
                comp = C.COMPANIONS.get(names[first])
                if comp and rng.random() < 0.55:
                    pick = name_to_idx[str(rng.choice(comp))]
                else:
                    pick = int(rng.choice(len(items), p=p))
                basket[pick] = basket.get(pick, 0) + 1
            for idx, qty in basket.items():
                row = items.iloc[idx]
                price = _price_on(row, day)
                lines.append((order_id, int(row["item_id"]), qty, price, float(row["unit_cost"])))

    orders_df = pd.DataFrame(
        orders, columns=["order_id", "order_ts", "order_date", "order_hour", "channel", "payment"]
    )
    lines_df = pd.DataFrame(lines, columns=["order_id", "item_id", "qty", "unit_price", "unit_cost"])
    log.info("generated %d orders, %d order lines", len(orders_df), len(lines_df))
    return {
        "dim_item": items.drop(columns=["base_weight"]),
        "fact_orders": orders_df,
        "fact_order_items": lines_df,
    }
