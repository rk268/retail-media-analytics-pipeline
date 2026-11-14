# Last-touch retail media attribution (synthetic example)

This reproducible SQLite-compatible SQL model assigns each order to the latest
eligible paid touch for the same **synthetic** customer identifier within the
inclusive seven-day lookback window. An order receives at most one attribution;
the deterministic tie-breaker is descending touch ID.

Inputs:
- `orders(order_id, customer_id, order_ts, revenue)` with unique order IDs.
- `ad_touches(touch_id, customer_id, touch_ts, channel, campaign_id)` with unique touch IDs.
- Timestamps must be consistently formatted UTC `YYYY-MM-DD HH:MM:SS`.
- Negative revenue rows are excluded; returns/refunds need separate modeling.

Output: `channel, campaign_id, attributed_orders, attributed_revenue`.

Run six executable SQL contract tests without Spark:
```bash
python -m unittest discover -s tests -p 'test_last_touch_attribution.py' -v
```

This is **descriptive attribution**, not causal incrementality or proof that ads
generated orders. It omits consent management, identity resolution, privacy
thresholds, bot filtering, viewability, cross-device deduplication, and organic
touches. Production models need validated identity, currency, time-zone, and
late-arriving-data policies. No actual advertising platform data is included.
