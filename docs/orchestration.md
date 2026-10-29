# Local PySpark pipeline orchestration

`src/pipeline_orchestrator.py` sequences the existing Bronze-to-Silver
and Silver-to-Gold Spark jobs. It adds bounded retries, per-stage timeouts,
stop-on-failure semantics, and append-only JSON Lines execution events.

## Run locally

Run from the repository root with `spark-submit` on PATH and Java configured:

```bash
python -m src.pipeline_orchestrator \
  --input data/raw/sample_campaign_metrics.csv \
  --silver data/silver/campaign_metrics \
  --gold data/gold/campaign_performance \
  --retries 1 \
  --timeout-seconds 900 \
  --events data/outputs/pipeline_events.jsonl
```

Only launch this after verifying the source CSV path and stage CLI arguments
match your installation. `--spark-submit` can point to an alternative executable.

## Monitoring and recovery

Each stage emits `started`, `succeeded`, or `failed` events, with a UTC timestamp,
run ID, stage index, attempt, and bounded failure message. A failed stage prevents
downstream execution. The runner exits non-zero after exhausting its retry budget.
The JSONL event stream supports later dashboards and log ingestion.

Retries are appropriate **only if each Spark stage is idempotent** for the chosen
output destinations. Validate write modes and partitions before enabling retries.
This simple local runner is not Airflow, does not ensure distributed exactly-once
execution, cannot coordinate overlapping process instances, and does not handle
remote cluster job status. It does not itself enforce data-quality validation;
the stage scripts retain that responsibility.

## Test

```bash
python -m unittest discover -s tests -p 'test_pipeline_orchestrator.py' -v
```

The tests mock subprocess execution, avoiding Spark and private infrastructure.
No proprietary data is included.
