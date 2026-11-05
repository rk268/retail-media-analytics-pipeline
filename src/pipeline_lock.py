"""Advisory single-host lock for the local Spark orchestration demo.

POSIX flock is automatically released on process exit or crash. It is not a
distributed lock and does not coordinate jobs on separate machines.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
from typing import Iterator


class PipelineAlreadyRunning(RuntimeError):
    """Another cooperating process currently holds the pipeline lock."""


@contextmanager
def pipeline_lock(path: str | Path) -> Iterator[None]:
    """Hold a nonblocking exclusive lock until the protected work finishes.

    Lock files remain on disk after release; their presence does not indicate
    an active owner. Never delete the file to "unlock" a running process.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(target, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            raise PipelineAlreadyRunning(f"Pipeline lock is held: {target}") from exc
        yield
    finally:
        if acquired:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
