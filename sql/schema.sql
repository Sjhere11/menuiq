-- MenuIQ star schema (SQLite). Loaded by menuiq.db.build_database().
DROP TABLE IF EXISTS fact_order_items;
DROP TABLE IF EXISTS fact_orders;
DROP TABLE IF EXISTS dim_item;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_item (
    item_id     INTEGER PRIMARY KEY,
    item_name   TEXT NOT NULL UNIQUE,
    category    TEXT NOT NULL,
    list_price  REAL NOT NULL CHECK (list_price > 0),
    unit_cost   REAL NOT NULL CHECK (unit_cost >= 0)
);

CREATE TABLE dim_date (
    date_key    TEXT PRIMARY KEY,           -- YYYY-MM-DD
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    dow         INTEGER NOT NULL,           -- 0 = Monday
    is_weekend  INTEGER NOT NULL
);

CREATE TABLE fact_orders (
    order_id    INTEGER PRIMARY KEY,
    order_ts    TEXT NOT NULL,
    order_date  TEXT NOT NULL REFERENCES dim_date(date_key),
    order_hour  INTEGER NOT NULL CHECK (order_hour BETWEEN 0 AND 23),
    channel     TEXT NOT NULL,
    payment     TEXT NOT NULL
);

CREATE TABLE fact_order_items (
    order_id    INTEGER NOT NULL REFERENCES fact_orders(order_id),
    item_id     INTEGER NOT NULL REFERENCES dim_item(item_id),
    qty         INTEGER NOT NULL CHECK (qty > 0),
    unit_price  REAL NOT NULL CHECK (unit_price > 0),
    unit_cost   REAL NOT NULL CHECK (unit_cost >= 0),
    PRIMARY KEY (order_id, item_id)
);

CREATE INDEX ix_orders_date ON fact_orders(order_date);
CREATE INDEX ix_lines_item ON fact_order_items(item_id);

-- Item x day grain, the workhorse view for most analysis.
CREATE VIEW v_item_daily AS
SELECT o.order_date,
       i.item_id,
       i.item_name,
       i.category,
       SUM(l.qty)                              AS units,
       SUM(l.qty * l.unit_price)               AS revenue,
       SUM(l.qty * (l.unit_price - l.unit_cost)) AS gross_profit
FROM fact_order_items l
JOIN fact_orders o USING (order_id)
JOIN dim_item    i USING (item_id)
GROUP BY o.order_date, i.item_id;
