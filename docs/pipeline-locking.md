# Single-host pipeline concurrency guard

The local orchestrator now uses an advisory POSIX `flock` lock around the
**entire** Bronze → Silver → Gold execution. A second cooperating invocation
using the same `--lock-file` exits nonzero before any Spark stages start.

```bash
python -m src.pipeline_orchestrator \
  --lock-file data/outputs/pipeline.lock \
  --events data/outputs/pipeline_events.jsonl
```

The default lock path is `data/outputs/pipeline.lock`. The operating system
releases the lock when the process exits, including after an unexpected crash.
The lock **file remains** afterward: file existence is not evidence of an
active lock. Do not delete it while a run may still be active.

This protects only cooperating processes sharing the same local filesystem and
lock path. It does not provide distributed coordination across machines,
containers with separate filesystems, or cluster schedulers. This implementation
requires POSIX `fcntl` (Linux/macOS); Windows users need WSL or a separate
locking backend. A terminated Spark launcher may leave child jobs running;
coordinate cluster-level execution independently before rerunning.

## Tests

```bash
python -m unittest discover -s tests -p 'test_pipeline_lock.py' -v
```

Tests spawn real local processes and verify mutual exclusion and release after
normal and exceptional exits. They do not require Spark or real advertising data.
