# Silver-to-Gold data quality gate

The Gold aggregation now runs `assert_quality(df)` before calculating campaign metrics.
The gate checks required columns, nonempty date/platform/campaign keys, nonnegative
non-null measures, and clicks no greater than impressions. Failures raise
`ValueError` with violation counts so the CLI stops instead of publishing
invalid campaign KPIs to the Gold Parquet path.

The reusable quality report is defined in [`src/data_quality.py`](../src/data_quality.py),
and tests for aggregation, invalid records, and zero denominators are in
[`tests/test_silver_to_gold_quality.py`](../tests/test_silver_to_gold_quality.py).

## Run the checks

```bash
python -m pytest -q
```

With the provided command line interface:

```bash
spark-submit src/silver_to_gold.py --input data/silver/campaign_metrics --output data/gold/campaign_performance
```

## Remaining limitations

This gate is intentionally fail-closed: it rejects the entire Gold build when
invalid Silver records exist, rather than silently dropping them. It does not
yet generate quarantined/rejected datasets, reconcile currency or attribution
windows, or validate account-level platform-specific measurement conventions.
Those require additional source adapters and controls.
