"""Charts, BI marts, and the static HTML dashboard."""

from __future__ import annotations

import base64
import html
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402
from . import db  # noqa: E402

log = logging.getLogger(__name__)

PALETTE = {"Star": "#2a9d8f", "Plowhorse": "#e9c46a", "Puzzle": "#457b9d", "Dog": "#e76f51"}
plt.rcParams.update(
    {
        "figure.dpi": 130,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9,
        "axes.titleweight": "bold",
    }
)


def _save(fig: plt.Figure, name: str) -> Path:
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = C.FIG_DIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_menu_matrix(cl: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for cls, g in cl.groupby("class"):
        ax.scatter(
            g["unit_share"] * 100,
            g["cm_per_unit"],
            s=40 + g["gross_profit"] / g["gross_profit"].max() * 400,
            color=PALETTE[cls],
            alpha=0.8,
            label=cls,
            edgecolor="white",
        )
    for r in cl.itertuples():
        ax.annotate(
            r.item_name,
            (r.unit_share * 100, r.cm_per_unit),
            fontsize=7,
            xytext=(4, 4),
            textcoords="offset points",
        )
    ax.axvline(cl.attrs["pop_threshold"] * 100, color="grey", ls="--", lw=0.8)
    ax.axhline(cl.attrs["cm_threshold"], color="grey", ls="--", lw=0.8)
    ax.set_xlabel("Share of units sold (%)")
    ax.set_ylabel("Contribution margin per unit (INR)")
    ax.set_title("Menu engineering matrix (bubble size = total gross profit)")
    ax.legend(title="Class", frameon=False)
    return _save(fig, "menu_matrix.png")


def fig_monthly(monthly: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    pos = list(range(len(monthly)))
    ax.bar(pos, monthly["revenue"] / 1e5, color="#a8dadc", label="Revenue (INR lakh)")
    ax.set_xticks(pos, monthly["month"].tolist())
    ax.set_ylabel("Revenue (INR lakh)")
    ax2 = ax.twinx()
    ax2.plot(pos, monthly["gross_margin_pct"], color="#1d3557", marker="o", label="Gross margin %")
    ax2.set_ylabel("Gross margin %")
    ax2.spines["right"].set_visible(True)
    ax.set_title("Monthly revenue and gross margin")
    ax.tick_params(axis="x", rotation=45)
    return _save(fig, "monthly_trend.png")


def fig_heatmap() -> Path:
    df = db.query(
        "SELECT d.dow, o.order_hour, COUNT(*) AS orders "
        "FROM fact_orders o JOIN dim_date d ON d.date_key = o.order_date GROUP BY 1, 2"
    )
    pivot = df.pivot(index="dow", columns="order_hour", values="orders")
    pivot.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    im = ax.imshow(pivot.values, aspect="auto", cmap="YlOrBr")
    ax.set_xticks(range(len(pivot.columns)), pivot.columns)
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.set_xlabel("Hour of day")
    ax.set_title("Orders by weekday and hour (staffing view)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    return _save(fig, "orders_heatmap.png")


def fig_pairs(pairs: pd.DataFrame) -> Path:
    top = pairs.head(10).iloc[::-1]
    labels = top["item_a"] + " + " + top["item_b"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(labels, top["lift"], color="#457b9d")
    ax.axvline(1, color="grey", ls="--", lw=0.8)
    ax.set_xlabel("Lift (1 = no association)")
    ax.set_title("Top item pairs by lift (support >= 0.5% of orders)")
    return _save(fig, "top_pairs.png")


def fig_elasticity(est: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    y = range(len(est))
    ax.errorbar(
        est["elasticity_est"],
        y,
        xerr=[est["elasticity_est"] - est["ci_low"], est["ci_high"] - est["elasticity_est"]],
        fmt="o",
        color="#1d3557",
        capsize=3,
        label="Estimate with 95% CI",
    )
    ax.scatter(est["true_elasticity"], y, marker="x", color="#e76f51", s=60, label="Planted true value")
    ax.set_yticks(list(y), est["item"])
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("Price elasticity of demand")
    ax.set_title("Price-test elasticity: recovered vs planted")
    ax.legend(frameon=False)
    return _save(fig, "elasticity.png")


def fig_forecast(metrics: pd.DataFrame, preds: pd.DataFrame, category: str = "Coffee") -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1, 2]})
    models = metrics["model"].tolist()
    axes[0].bar(
        range(len(models)), metrics["wape"] * 100, color=["#2a9d8f", "#a8dadc", "#e9c46a"][: len(models)]
    )
    axes[0].set_xticks(range(len(models)), models)
    axes[0].set_ylabel("WAPE % (lower is better)")
    axes[0].set_title("Walk-forward error, 7-day horizon")
    axes[0].tick_params(axis="x", rotation=20)
    sub = preds[preds["category"] == category].sort_values("date").tail(56)
    axes[1].plot(sub["date"], sub["units"], color="black", label="Actual")
    axes[1].plot(sub["date"], sub["pred_gbm"], color="#2a9d8f", label="Gradient boosting")
    axes[1].plot(sub["date"], sub["pred_seasonal_naive"], color="#e76f51", ls=":", label="Seasonal naive")
    axes[1].set_title(f"{category}: last 8 weeks, forecast vs actual")
    axes[1].legend(frameon=False)
    axes[1].tick_params(axis="x", rotation=30)
    return _save(fig, "forecast.png")


def write_marts(tables: dict[str, pd.DataFrame]) -> None:
    C.MARTS_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(C.MARTS_DIR / f"{name}.csv", index=False)
    log.info("wrote %d BI marts to %s", len(tables), C.MARTS_DIR)


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _table(df: pd.DataFrame, fmt: dict[str, str] | None = None) -> str:
    fmt = fmt or {}
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, r in df.iterrows():
        cells = ""
        for c in df.columns:
            v = r[c]
            cells += f"<td>{html.escape(fmt[c].format(v) if c in fmt else str(v))}</td>"
        body += f"<tr>{cells}</tr>"
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def write_dashboard(kpis: dict[str, str], figs: dict[str, Path], tables: dict[str, str]) -> Path:
    cards = "".join(
        f'<div class="card"><div class="k">{html.escape(v)}</div><div class="l">{html.escape(k)}</div></div>'
        for k, v in kpis.items()
    )
    sections = ""
    for title, fig in figs.items():
        sections += f'<h2>{html.escape(title)}</h2><img src="data:image/png;base64,{_b64(fig)}" alt="{html.escape(title)}">'
        if title in tables:
            sections += tables[title]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MenuIQ dashboard</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#1d3557;background:#fafafa}}
h1{{margin-bottom:.2rem}} .sub{{color:#555;margin-bottom:1.5rem}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:1.5rem}}
.card{{background:#fff;border:1px solid #e3e3e3;border-radius:10px;padding:14px}}
.k{{font-size:1.5rem;font-weight:700}} .l{{color:#666;font-size:.85rem}}
img{{max-width:100%;background:#fff;border:1px solid #e3e3e3;border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:.85rem;margin:.6rem 0 1.4rem;background:#fff}}
th,td{{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}} th{{background:#f1f5f9}}
.note{{background:#fff8e1;border:1px solid #ffe082;padding:10px 14px;border-radius:8px;font-size:.9rem}}
</style></head><body>
<h1>MenuIQ: cafe menu and demand analytics</h1>
<div class="sub">Jan to Dec 2025, simulated POS data for one independent cafe</div>
<div class="note"><b>Synthetic data.</b> Every number here comes from a simulation with documented assumptions, not a real business.</div>
<div class="cards" style="margin-top:1rem">{cards}</div>{sections}
</body></html>"""
    path = C.REPORTS_DIR / "dashboard.html"
    path.write_text(page, encoding="utf-8")
    log.info("dashboard written to %s", path)
    return path
