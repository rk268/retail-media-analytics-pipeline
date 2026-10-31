# Pipeline health monitoring and dashboard export

This monitoring utility consumes the JSONL events produced by
`src/pipeline_orchestrator.py`. It validates each event, reconstructs
per-stage attempts and retries, detects stalled executions, and atomically
publishes a dashboard-ready JSON snapshot. It uses only the Python standard
library and does not need Spark to run.

## Example

First run the orchestrator against the **simulated** sample data. Then:

```bash
python -m src.pipeline_monitor \
  --events data/outputs/pipeline_events.jsonl \
  --output data/outputs/pipeline_health.json \
  --expected-stages 2 \
  --stale-after-seconds 600 \
  --fail-on-unhealthy
```

Exit code 0 indicates all observed runs succeeded (when the flag is enabled).
Exit code 1 indicates an empty log or at least one unhealthy run.
Exit code 2 indicates malformed events or a read/write error; the previous
dashboard file is preserved if validation fails.

The JSON snapshot contains a schema version, generation time, latest run ID,
counts of succeeded/failed/running/stalled/incomplete runs, and a list of
runs with stage status, attempt counts, retries, bounded error text, and
observed event durations. This is suitable for a Power BI/BI JSON ingestion
example or a scheduled health check. It does not claim any real campaign
performance.

## Semantics and limitations

- A failure is a **snapshot** state: the orchestrator might later retry.
- An unfinished attempt is *stalled* only after the configured time threshold.
- A run succeeds only after every expected stage has a success event.
- Timestamps must be timezone-aware; per-run event order and retry sequencing
  are validated. Invalid logs fail closed instead of silently dropping events.
- A successful process does not imply upstream source quality or correct
  business metrics. The pipeline's own quality checks remain authoritative.
- This is a **local** monitoring example, not distributed locking, a job
  scheduler, or a replacement for production telemetry.
- The JSONL log may include command arguments and error text. Do not publish
  actual production logs containing credentials, customer data, or internal paths.

## Tests

```bash
python -m unittest discover -s tests -p 'test_pipeline_monitor.py' -v
```

The tests use synthetic events and a fixed clock; no external services or
employer data are required.
