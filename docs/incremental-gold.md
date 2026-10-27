# Incremental, date-partitioned Gold (synthetic portfolio example)

The original src/silver_to_gold.py builds **all-time** campaign KPIs. src/incremental_gold.py instead publishes **daily** campaign KPIs, with one Parquet partition per event_date. A rerun of one day replaces that day's partition without deleting other dates. This is a separate output dataset, not a drop-in replacement for the all-time Gold schema.

## Run from the repository root

Requires Java 17+, Python 3.11 and the dependencies in requirements.txt. First produce Silver using src/bronze_to_silver.py.

    python -m src.incremental_gold --input data/silver/campaign_metrics --output data/gold/daily_campaign_performance --date 2026-10-01

    python -m pytest -q tests/test_incremental_gold.py

Rerun with --date 2026-10-02 to add or replace another date. The --date argument is required to prevent accidental full-table overwrites. The output is partitioned as event_date=YYYY-MM-DD/ and has daily sums plus CTR, CPC, CPM, conversion rate, CPA and ROAS, computed **after** aggregation. Downstream dashboards must use the daily grain; summing ratios is incorrect.

## Guarantees and limitations

- The entire input Silver dataset passes the existing quality gate before selecting the requested date. The selected day additionally rejects duplicate campaign-day keys, blank campaign names and nonfinite money values. Empty target dates fail without writing.
- Spark's dynamic partition-overwrite mode replaces only the selected partition on successful reruns, preserving other dates. Repeated execution of the same input does not append duplicates.
- **Plain Parquet is not transactional**: interrupted writes, concurrent writers or failures can leave an incomplete partition. For production use a transactional lakehouse table (Delta Lake/Iceberg) with an atomic replace-partition operation, orchestration locks and retry/checkpoint handling.
- This sample scans Silver to validate it; a production partition-pruned quality gate would need a separate full-table monitoring strategy. No claim of production-scale performance is made.
- All examples and tests use fictional data; no employer exports or performance results are included.
