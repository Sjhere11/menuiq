"""End-to-end pipeline: simulate -> SQLite -> analyse -> report.

Run with:  python -m menuiq.pipeline
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from . import basket, db, forecast, generate, menu_engineering, pricing, report
from . import config as C

log = logging.getLogger("menuiq")


def run() -> dict:
    tables = generate.generate()
    db.build_database(tables)

    # SQL layer (also shown in the README).
    kpi_sets = db.run_sql_file(C.SQL_DIR / "01_kpis_and_trends.sql")
    monthly, cat_profit = kpi_sets[0], kpi_sets[1]
    basket_sets = db.run_sql_file(C.SQL_DIR / "02_basket_and_peak_hours.sql")
    channel_aov = basket_sets[0]

    # Menu engineering.
    cl = menu_engineering.classify(menu_engineering.item_summary())

    # Basket analysis.
    pairs = basket.pair_rules(basket.basket_matrix())
    pair_check = basket.planted_pair_recall(pairs, 10)

    # Price experiment and scenarios.
    est, pooled = pricing.estimate_elasticities()
    base = pricing.reprice_scenario(cl, pooled["estimate"], 0.05)
    sens = pd.DataFrame(
        [
            {
                "case": name,
                "elasticity": e,
                "annual_profit_change_inr": float(
                    pricing.reprice_scenario(cl, e, 0.05)["profit_change"].sum()
                ),
            }
            for name, e in (
                ("pooled CI low (more elastic)", pooled["ci_low"]),
                ("pooled estimate", pooled["estimate"]),
                ("pooled CI high (less elastic)", pooled["ci_high"]),
            )
        ]
    )
    breakeven = pricing.breakeven_elasticity(cl, 0.05)

    # Forecasting.
    feat = forecast.build_features(forecast.category_daily())
    metrics, preds = forecast.walk_forward(feat)
    cat_wape = forecast.per_category_wape(preds)

    # Outputs.
    total_rev = float(monthly["revenue"].sum())
    total_orders = int(db.query("SELECT COUNT(*) AS n FROM fact_orders")["n"].iloc[0])
    gp = float(cl["gross_profit"].sum())
    figs = {
        "Menu engineering matrix": report.fig_menu_matrix(cl),
        "Monthly revenue and gross margin": report.fig_monthly(monthly),
        "Orders by weekday and hour": report.fig_heatmap(),
        "Items bought together": report.fig_pairs(pairs),
        "Price experiment: elasticity": report.fig_elasticity(est),
        "7-day demand forecast": report.fig_forecast(metrics, preds),
    }
    class_counts = cl["class"].value_counts().to_dict()
    best = metrics.iloc[0]
    naive = metrics[metrics["model"] == "seasonal_naive"].iloc[0]
    kpis = {
        "Orders": f"{total_orders:,}",
        "Revenue (INR lakh)": f"{total_rev / 1e5:,.1f}",
        "Gross margin": f"{100 * gp / total_rev:.1f}%",
        "Avg order value (INR)": f"{total_rev / total_orders:,.0f}",
        "Forecast WAPE (best)": f"{100 * best['wape']:.1f}%",
        "Items: Star / Plowhorse / Puzzle / Dog": " / ".join(
            str(class_counts.get(k, 0)) for k in ["Star", "Plowhorse", "Puzzle", "Dog"]
        ),
    }
    tables = {
        "Menu engineering matrix": report._table(
            cl[["item_name", "category", "units", "avg_price", "cm_per_unit", "margin_pct", "class"]],
            {"avg_price": "{:.0f}", "cm_per_unit": "{:.1f}", "margin_pct": "{:.1f}", "units": "{:,.0f}"},
        ),
        "Price experiment: elasticity": report._table(
            est[
                [
                    "item",
                    "price_change_pct",
                    "elasticity_est",
                    "ci_low",
                    "ci_high",
                    "true_elasticity",
                    "true_in_ci",
                ]
            ],
            {
                c: "{:.2f}"
                for c in ["price_change_pct", "elasticity_est", "ci_low", "ci_high", "true_elasticity"]
            },
        ),
        "7-day demand forecast": report._table(
            metrics,
            {"wape": "{:.3f}", "mae_units": "{:.1f}", "wape_fold_min": "{:.3f}", "wape_fold_max": "{:.3f}"},
        ),
    }
    report.write_dashboard(kpis, figs, tables)
    report.write_marts(
        {
            "mart_item_performance": cl.drop(columns=["action"]),
            "mart_monthly_kpis": monthly,
            "mart_category_profit": cat_profit,
            "mart_item_pairs": pairs,
            "mart_price_elasticity": est,
            "mart_forecast_backtest": preds[
                ["date", "category", "units", "pred_gbm", "pred_seasonal_naive", "pred_4wk_avg", "fold"]
            ],
            "mart_channel_aov": channel_aov,
        }
    )

    summary = {
        "orders": total_orders,
        "revenue_inr": round(total_rev),
        "gross_margin_pct": round(100 * gp / total_rev, 2),
        "class_counts": class_counts,
        "classes": cl[["item_name", "class", "unit_share", "cm_per_unit", "margin_pct"]]
        .round(4)
        .to_dict("records"),
        "thresholds": {"popularity": cl.attrs["pop_threshold"], "cm_per_unit": cl.attrs["cm_threshold"]},
        "elasticity": est.round(3).to_dict("records"),
        "elasticity_pooled": {k: round(v, 3) for k, v in pooled.items()},
        "reprice_base_annual_profit_change": round(float(base["profit_change"].sum())),
        "reprice_sensitivity": [
            {
                "case": r["case"],
                "elasticity": round(r["elasticity"], 2),
                "annual_profit_change_inr": round(r["annual_profit_change_inr"]),
            }
            for r in sens.to_dict("records")
        ],
        "reprice_breakeven_elasticity": round(breakeven, 2),
        "reprice_detail": base.round(1).to_dict("records"),
        "pair_validation": pair_check,
        "forecast_metrics": metrics.round(4).to_dict("records"),
        "forecast_by_category": cat_wape.round(4).to_dict("records"),
        "forecast_improvement_vs_naive_pct": round(100 * (1 - best["wape"] / naive["wape"]), 1),
        "top_pairs": pairs.head(8).round(3).to_dict("records"),
        "category_profit": cat_profit.to_dict("records"),
        "channel_aov": channel_aov.to_dict("records"),
    }
    (C.REPORTS_DIR / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = run()
    log.info("done: %d orders, margin %.1f%%", s["orders"], s["gross_margin_pct"])


if __name__ == "__main__":
    main()
