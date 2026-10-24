# Simulated ad-platform source adapters

The Python standard-library module src/source_adapters.py normalizes **fictional Google-like and Meta-like CSV exports** into the exact nine-column canonical schema accepted by src/bronze_to_silver.py. No vendor API is called, no credentials are used, and the fixtures are entirely invented. The example column names are **not** guaranteed to match actual platform exports or attribution semantics.

## Run

First, normalize the fabricated exports:

    python -m src.source_adapters --google data/raw/mock_google_ads.csv --meta data/raw/mock_meta_ads.csv --output data/raw/normalized_platform_exports.csv

Then feed the canonical CSV to the existing PySpark pipeline:

    spark-submit src/bronze_to_silver.py --input data/raw/normalized_platform_exports.csv --output data/silver/normalized_platform_exports

Run the adapter tests:

    python -m pytest tests/test_source_adapters.py -q

## Contract and validation

- Each source uses an explicit column mapping. Google-like cost_micros is integer micro-USD, divided by 1,000,000; Meta-like spend_usd is already USD. Both become two-decimal strings using ROUND_HALF_UP. This example assumes the same USD currency and reporting window across sources; **production data requires explicit currency conversion and attribution alignment**.
- Campaign ID and name must be nonempty. Dates must be valid ISO calendar dates. Count fields must be nonnegative integers; clicks cannot exceed impressions in this simplified demo. Spend/revenue must be finite and nonnegative. Conversion counts are not capped at clicks because attribution may differ.
- Duplicate (event_date, platform, campaign_id) keys, empty files, malformed rows and missing/duplicate headers **fail the batch**, rather than silently deduplicating. The output is written to a temporary file and atomically replaced only after all input rows pass validation.
- This adapter is a local batch ingestion example. It does not implement incremental state, API pagination, authentication, currency normalization across markets, or production error quarantine.
