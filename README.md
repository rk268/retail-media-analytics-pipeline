# Retail Media Analytics Pipeline

A portfolio project that models a modern cross-channel Retail Media analytics workflow with **PySpark, SQL, and medallion architecture**.

The project uses simulated campaign data from Google Ads, Meta Ads, Pinterest, and Snapchat so the pipeline can be shared publicly without exposing proprietary data.

## Architecture

```text
Raw ad-platform exports
        |
        v
+------------------+
| Bronze           |  Raw CSV ingestion + source metadata
+------------------+
        |
        v
+------------------+
| Silver           |  Schema normalization, validation, KPI preparation
+------------------+
        |
        v
+------------------+
| Gold             |  Channel / campaign aggregates for analytics
+------------------+
        |
        +----> SQL analytics
        +----> BI / reporting layer
```

## Metrics

The Gold layer prepares common cross-platform metrics including:

- CTR = clicks / impressions
- CPC = spend / clicks
- CPM = spend / impressions × 1,000
- Conversion Rate = conversions / clicks
- CPA = spend / conversions
- ROAS = revenue / spend

## Project structure

```text
.
├── data/raw/                  # Simulated source extracts
├── sql/                       # Analyst-facing SQL examples
├── src/
│   ├── bronze_to_silver.py    # Ingestion + normalization
│   └── silver_to_gold.py      # Aggregation + KPI layer
├── tests/                     # Lightweight business-rule tests
├── .github/workflows/         # CI
└── requirements.txt
```

## Run locally

1. Install Java 17+ and Python 3.10+.
2. Create an environment and install dependencies:

```bash
pip install -r requirements.txt
```

3. Build Silver data:

```bash
spark-submit src/bronze_to_silver.py \
  --input data/raw/sample_campaign_metrics.csv \
  --output data/silver/campaign_metrics
```

4. Build Gold data:

```bash
spark-submit src/silver_to_gold.py \
  --input data/silver/campaign_metrics \
  --output data/gold/campaign_performance
```

## Data model

The simulated input is intentionally normalized to a common schema:

```text
event_date, platform, campaign_id, campaign_name,
impressions, clicks, spend, conversions, revenue
```

Real production pipelines would typically ingest each platform's native export/API schema separately and normalize fields in the Silver layer.

## Roadmap

- [x] Initial PySpark Bronze → Silver normalization
- [x] Gold cross-channel KPI aggregation
- [x] SQL analyst query
- [x] CI business-rule tests
- [ ] Add source-specific adapters for Google / Meta / Pinterest / Snapchat schemas
- [ ] Add data-quality expectations and quarantine records
- [ ] Add incremental processing and partition strategy
- [ ] Add attribution / incrementality example
- [ ] Add orchestration example
- [ ] Add dashboard-ready semantic layer

## Why this project

Retail Media reporting often requires combining platforms that use different naming, schemas, attribution windows, and measurement logic. This repo demonstrates the engineering layer needed before cross-channel metrics can be compared responsibly.

> Note: All data in this repository is simulated for demonstration purposes.
