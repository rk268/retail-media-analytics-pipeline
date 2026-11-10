# Output manifests for recovery checks

`src/output_manifest.py` produces SHA-256 inventories for **local** Spark
output directories. Use this alongside the event-based recovery planner to
confirm that an upstream output has not changed since its manifest was captured.

```bash
python -m src.output_manifest data/gold/campaign_performance data/outputs/gold-manifest.json
python -m src.output_manifest data/gold/campaign_performance data/outputs/gold-manifest.json --verify
python -m unittest tests.test_output_manifest -v
```

The manifest includes sorted relative paths, byte lengths, and SHA-256 digests.
Writing uses a temporary file and atomic replacement on the destination
filesystem. The manifest must live **outside** the inventoried output directory.
Verification fails for added, removed, or modified files; symlinks are rejected.

## Recovery workflow

1. Complete a successful stage and capture its manifest after writers finish.
2. Store the manifest independently from the stage output.
3. Before manually skipping an upstream stage, verify its saved manifest against
   the output and inspect the pipeline recovery planner's event-based recommendation.
4. If any check fails, rerun the upstream stage from a safe boundary.

This is not a transaction protocol or an automatic resume mechanism. A matching
manifest does not prove business correctness, successful randomization, or
absence of concurrent writes. Use stable completed directories only; avoid
manifesting outputs while Spark jobs are active. The files are not signed and
must be stored in a trusted location. Remote object storage requires a
separate adapter with consistent listing/version semantics. Examples are
synthetic and contain no employer data.
