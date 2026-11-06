-- 3. Average order value and items per order by channel.
WITH order_totals AS (
    SELECT o.order_id, o.channel,
           SUM(l.qty)                  AS items,
           SUM(l.qty * l.unit_price)   AS order_value
    FROM fact_orders o
    JOIN fact_order_items l USING (order_id)
    GROUP BY o.order_id
)
SELECT channel,
       COUNT(*)                         AS orders,
       ROUND(AVG(order_value), 1)       AS avg_order_value,
       ROUND(AVG(items), 2)             AS avg_items
FROM order_totals
GROUP BY channel
ORDER BY orders DESC;

-- 4. Orders by hour with share of the day (peak-hour staffing view).
WITH hourly AS (
    SELECT order_hour, COUNT(*) AS orders FROM fact_orders GROUP BY order_hour
)
SELECT order_hour,
       orders,
       ROUND(100.0 * orders / SUM(orders) OVER (), 1)               AS pct_of_orders,
       ROUND(100.0 * SUM(orders) OVER (ORDER BY order_hour)
             / SUM(orders) OVER (), 1)                              AS cumulative_pct
FROM hourly
ORDER BY order_hour;

-- 5. Top item pairs by joint orders (self-join on order_id, item_a < item_b).
SELECT a.item_id AS item_a, b.item_id AS item_b, COUNT(*) AS together
FROM fact_order_items a
JOIN fact_order_items b
  ON a.order_id = b.order_id AND a.item_id < b.item_id
GROUP BY a.item_id, b.item_id
ORDER BY together DESC
LIMIT 10;
