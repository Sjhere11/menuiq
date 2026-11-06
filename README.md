# MenuIQ: menu engineering, price elasticity and demand forecasting for a cafe

[![CI](https://github.com/Sjhere11/menuiq/actions/workflows/ci.yml/badge.svg)](https://github.com/Sjhere11/menuiq/actions/workflows/ci.yml)

End-to-end analytics project for an independent cafe: SQL star schema, menu engineering matrix,
market-basket analysis, a price-elasticity estimate from a natural experiment, a leakage-safe
7-day demand forecast, a profit scenario with sensitivity analysis, and BI-ready data marts.

> **The data is synthetic.** It is simulated from documented assumptions (`src/menuiq/config.py`), not taken
> from a real business. That is deliberate: the true price elasticities and true item pairings are known,
> so each method can be checked against ground truth. Nothing here should be read as a claim about a real cafe.

Open [`reports/dashboard.html`](reports/dashboard.html) after cloning for the full visual report.

## The business question

A cafe owner has 26 menu items and a year of POS sales. Which items deserve menu space, which should be
repriced or reworked, what sells together, and how much stock should be ready next week?

## Results on the simulated year (2025)

| Metric | Value |
|---|---|
| Orders / order lines | 60,827 / 109,941 |
| Revenue / gross margin | INR 1.04 crore / 68.9% |
| Average order value | INR 172 |
| Menu classes | 7 Star, 8 Plowhorse, 10 Puzzle, 1 Dog |
| Best 7-day forecast error (WAPE) | 14.4% (gradient boosting) |

**Menu engineering.** Masala Chai is the volume leader (12.0% of units) but earns only INR 33 per unit, so it
is a Plowhorse. Cold Brew earns INR 142 per unit on 0.8% of units, a Puzzle worth promoting. Coffee delivers
30.2% of gross profit at a 74.5% margin; Meals have the weakest category margin at 56.8%.

**Basket analysis.** Brownie + Latte has the highest lift (3.8). Cold Coffee + Veg Burger is the strongest pair
by volume (908 joint orders, lift 2.7). Both are bundle candidates.

**Price experiment.** Four items were repriced by about 10% on 1 July. Individual estimates are imprecise
(see the chart), so the pooled elasticity is the one to use: **-0.97, 95% interval [-1.63, -0.23]**, against a
planted average of -1.05.

**Repricing scenario.** Raising every Plowhorse price by 5% changes annual gross profit by about **+INR 42.6k**
at the pooled elasticity. Across the 95% interval the result runs from **-INR 25.0k to +INR 120.7k**, and the
change breaks even at an elasticity of about -1.39. The honest conclusion is "run a controlled test first",
not "raise prices".

**Forecast.** Walk-forward WAPE over four 28-day folds:

| Model | WAPE |
|---|---|
| Seasonal naive (same weekday last week) | 19.0% |
| 4-week average of same weekday | 14.8% |
| Gradient boosting (this project) | **14.4%** |

Gradient boosting is 24.5% better than the seasonal-naive baseline but only about 3% better than the simple
4-week average. Much of the remaining error is Poisson noise in daily counts that no model can remove. It
helps least for Cold Drinks (24.2% vs 24.6%), because the training window holds no prior year of the summer
spike.

## Validation against ground truth

Because the generator's true parameters are known, `tests/test_pipeline_end_to_end.py` asserts that the analysis
recovers them:

- the pooled elasticity interval contains the planted mean elasticity;
- at least 8 of the top 10 item pairs by lift are planted companions (the run finds 10 of 10);
- the forecast beats the seasonal-naive baseline out of sample;
- forecast features cannot see data newer than the 7-day horizon (tested by tampering with recent values).

## Methods

| Stage | Method |
|---|---|
| Storage | SQLite star schema with constraints, indexes, and a daily item view (`sql/schema.sql`) |
| SQL analysis | CTEs and window functions: MoM growth with `LAG`, profit share with `RANK`, cumulative hourly share, self-join item pairs (`sql/01_*.sql`, `sql/02_*.sql`) |
| Menu engineering | Kasavana-Smith matrix: popularity >= 70% of equal share, margin vs sales-weighted average contribution margin |
| Basket analysis | Support, confidence and lift from a boolean order-item matrix, minimum support 0.5% |
| Elasticity | Difference-in-differences on units per 100 orders, six weeks either side, unchanged same-category items as controls, 2,000-draw bootstrap |
| Forecast | HistGradientBoosting on lags >= 7 days, rolling means, weekday and event flags; expanding-window walk-forward with refit per fold |
| Scenario | Plowhorse repricing with `(1 + rise) ** elasticity` demand response, a sensitivity table, and a break-even solver |

## Limitations

- Synthetic data: findings describe the simulation, and the value of the project is the method.
- The menu matrix compares items across categories, so high-priced categories (Meals) skew toward "Puzzle".
  A within-category variant is a natural extension.
- The elasticity design uses one price change, six-week windows, and category controls. Single-item intervals
  are wide (Brownie's includes zero), which is why the scenario uses the pooled estimate.
- The scenario ignores cannibalisation, competitor response, and any effect on footfall.
- One year of history means no prior-year seasonality to learn from.

## Run it

```bash
pip install -r requirements-dev.txt
pip install -e .
python -m menuiq.pipeline      # simulate, load, analyse, write reports/ and bi_marts/
pytest --cov=src               # 25 tests
ruff check src tests
```

Developed and tested on Python 3.13; CI runs 3.11 to 3.13. The pipeline takes about 12 seconds.

## Power BI / Tableau

`bi_marts/` holds seven tidy CSVs, ready to load as a star-like model: item performance, monthly KPIs,
category profit, item pairs, price elasticity, forecast backtest, and channel order value. No `.pbix` or
`.twbx` file is included.

## Data

The simulated dataset is included so nothing has to be run to inspect it: `data/menuiq.db` (SQLite) and the same four tables as CSV in `data/raw/`. Regenerate it with `python -m menuiq.pipeline` (seeded, so the output is identical).

## Layout

```
src/menuiq/   config, generate, db, menu_engineering, basket, pricing, forecast, report, pipeline
sql/          schema + analytical queries
tests/        unit and integration tests, including the ground-truth validation
reports/      dashboard.html, figures, summary.json
bi_marts/     CSV extracts for Power BI / Tableau
data/         simulated dataset: SQLite database and raw CSV tables
```

## Licence

MIT
