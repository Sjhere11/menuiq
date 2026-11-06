-- 1. Monthly revenue, gross margin %, and month-over-month growth.
WITH monthly AS (
    SELECT substr(order_date, 1, 7)  AS month,
           SUM(revenue)              AS revenue,
           SUM(gross_profit)         AS gross_profit
    FROM v_item_daily
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 0)                                          AS revenue,
       ROUND(100.0 * gross_profit / revenue, 1)                   AS gross_margin_pct,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / LAG(revenue) OVER (ORDER BY month), 1)             AS mom_growth_pct
FROM monthly
ORDER BY month;

-- 2. Revenue and profit share by category, ranked by profit.
SELECT category,
       ROUND(SUM(revenue), 0)                                     AS revenue,
       ROUND(SUM(gross_profit), 0)                                AS gross_profit,
       ROUND(100.0 * SUM(gross_profit) / SUM(revenue), 1)         AS margin_pct,
       ROUND(100.0 * SUM(gross_profit)
             / SUM(SUM(gross_profit)) OVER (), 1)                 AS profit_share_pct,
       RANK() OVER (ORDER BY SUM(gross_profit) DESC)              AS profit_rank
FROM v_item_daily
GROUP BY category
ORDER BY profit_rank;
