# Retail media data-quality gate

`src/data_quality.py` adds an explicit, reusable validation step for normalized **silver** campaign data. It is intentionally separate from the existing transformations so teams can inspect the report before choosing to fail or quarantine a batch.

## Checks

- Required schema columns exist.
- Event date, platform and campaign ID are non-null; platform and campaign ID are nonblank.
- Impressions, clicks, spend, conversions and revenue are non-null and nonnegative.
- Clicks do not exceed impressions.

`quality_report(df)` returns a one-row Spark DataFrame containing total row count and violation counts. `assert_quality(df)` raises `ValueError` on any violation and otherwise returns the counts as a Python dictionary. Counts represent checks, **not unique bad rows**: one observation can violate several rules.

## Example

```python
from src.data_quality import quality_report, assert_quality

report = quality_report(silver_df)
report.show(truncate=False)
assert_quality(silver_df)  # Raises if invalid; only then write gold output
```

## Test locally

```bash
pip install pyspark pytest
python -m pytest tests/test_data_quality.py -q
```

The fixture uses a local Spark session and synthetic data. This module does not assert that tests have been run in CI, and it does not yet integrate the gate into the command-line pipeline. Future improvements: quarantine records, source-specific thresholds, and CI execution.
