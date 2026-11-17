# SHA-256 manifest-gated recovery planning

`src/manifest_recovery.py` integrates the existing read-only recovery planner
with `src/output_manifest.py`. It **refuses to skip an upstream stage**
unless its output directory still matches a previously recorded SHA-256 manifest.

## Example

After stage 1 finishes successfully, while its output is quiescent:

```bash
python -m src.output_manifest data/silver/campaign_metrics data/outputs/silver-manifest.json
```

After a later stage fails and **after confirming the original process has stopped**:

```bash
python -m src.manifest_recovery \
  --events data/outputs/pipeline_events.jsonl \
  --run-id YOUR_RUN_ID \
  --expected-stages 2 \
  --stage-artifact 1 data/silver/campaign_metrics data/outputs/silver-manifest.json
```

The command emits a JSON restart *plan*, not a Spark invocation. The manifest
must be created before failure/recovery and stored outside the output tree.
No manifest, malformed manifest, changed file, added/deleted file, or symlink
evidence means recovery is refused. A failure at stage 1 needs no skipped-stage
manifest. Fully successful runs return a no-op.

## Boundaries

SHA-256 confirms byte-level consistency with a recorded snapshot, **not**
correctness, data lineage, completeness, or freshness of the original snapshot.
An operator must independently validate input snapshots, expected partition
coverage, semantic quality, lock ownership, and idempotent destination writes.
A manifest and its output must be protected against simultaneous alteration.
This is a local-file demonstration, not distributed recovery or a transactional
data-lake commit protocol.

Tests use only synthetic local files:

```bash
python -m unittest discover -s tests -p 'test_manifest_recovery.py' -v
```
