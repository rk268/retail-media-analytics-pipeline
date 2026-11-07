# Conservative pipeline recovery planning

The local pipeline already emits JSONL stage events and provides monitoring.
`src/pipeline_recovery.py` adds **read-only restart planning** based on the
validated monitoring summary. It never launches Spark or mutates output data.

## Example

After checking the original process has stopped and verifying the Silver
artifact for stage 1 (correct input snapshot, schema, partition, completeness):

```bash
python -m src.pipeline_recovery \
  --events data/outputs/pipeline_events.jsonl \
  --run-id YOUR_RUN_ID \
  --expected-stages 2 \
  --verified-stage 1
```

The command emits JSON identifying the first stage that needs a manual rerun.
If the first stage failed, no upstream verification is needed. A completed
run produces a no-op plan.

## Safety constraints

- Reject unknown or duplicate run IDs and inconsistent stage inventories.
- Reject running/stalled stages: first confirm the original process has ended.
- Refuse to skip an upstream successful stage unless its output has been
  explicitly verified by the operator.
- Refuse unexpected downstream activity following a failure.
- The `--verified-stage` flag is an **operator assertion**, not an automatic
  check. This code does not inspect data files or guarantee idempotency.
- Recheck source snapshot, write modes, partitions, downstream consumers, and
  lock ownership before any manual rerun. For distributed recovery, use a
  durable orchestrator and transactional storage.

Tests are synthetic and require no Spark cluster.
