-- Synthetic retail media: last eligible paid touch within seven days before an order.
-- Revenue is assigned to exactly one touch per order (no cross-device identity).
WITH eligible AS (
 SELECT o.order_id, o.customer_id, o.order_ts, o.revenue,
        t.touch_id, t.channel, t.campaign_id, t.touch_ts,
        ROW_NUMBER() OVER (
          PARTITION BY o.order_id
          ORDER BY t.touch_ts DESC, t.touch_id DESC
        ) AS touch_rank
 FROM orders o
 JOIN ad_touches t ON t.customer_id = o.customer_id
 WHERE t.touch_ts <= o.order_ts
   AND t.touch_ts >= datetime(o.order_ts, '-7 days')
   AND o.revenue >= 0
),
last_touch AS (
 SELECT order_id, channel, campaign_id, revenue
 FROM eligible WHERE touch_rank = 1
)
SELECT channel, campaign_id,
       COUNT(*) AS attributed_orders,
       ROUND(SUM(revenue), 2) AS attributed_revenue
FROM last_touch
GROUP BY channel, campaign_id
ORDER BY channel, campaign_id;
