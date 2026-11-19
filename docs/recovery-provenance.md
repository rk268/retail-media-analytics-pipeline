# Run-bound recovery provenance

The existing manifest-gated recovery planner checks upstream output bytes.
`src/recovery_provenance.py` adds a second safety gate: skipped stages must
have **run-specific evidence** that their input and output manifests still
match, and the evidence must fall inside a configurable freshness window.

## Integration

After a successful stage, create SHA-256 manifests for its input and output
directories using `src.output_manifest.write_manifest`. Store manifests
outside both directories. Then call `record_evidence(run_id=..., stage=...,
input_dir=..., input_manifest=..., output_dir=..., output_manifest=...)`.
Persist its returned JSON in a protected run-specific location.

For manual restart planning, call:

```python
plan_with_provenance(
    monitor_summary, run_id,
    {1: (silver_dir, silver_manifest, raw_dir, raw_manifest)},
    {1: evidence_record},
    max_age_seconds=86400,
)
```

This returns a restart plan only when both the existing output verification
and the new input/run/freshness checks pass. Missing, modified, expired, or
future-dated evidence refuses recovery. It never starts a Spark job.

Run isolated tests with:

```bash
python -m unittest discover -s tests -p 'test_recovery_provenance.py' -v
```

## Security and operational limits

SHA-256 manifests detect accidental drift; they do **not** authenticate
evidence against a malicious actor able to rewrite the files and evidence.
Store records in access-controlled immutable storage for production use.
Manifest checks are point-in-time; coordinate them with existing pipeline
locks and snapshot-consistent storage to avoid time-of-check/time-of-use
races. Freshness is a configurable policy, not proof of data correctness.
This module handles local files, not object-store version IDs or distributed
exactly-once guarantees. All examples and tests use synthetic data.
