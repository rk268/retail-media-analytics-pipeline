"""Local sequential orchestration for the retail-media PySpark demo.

The runner does not claim to be a distributed scheduler. It makes individual
spark-submit stages observable, bounded, and resumable through explicit reruns.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Sequence


STAGES = (
    "src/bronze_to_silver.py",
    "src/silver_to_gold.py",
)


class PipelineFailure(RuntimeError):
    """A required pipeline stage failed after its retry budget."""


def run_pipeline(
    commands: Sequence[Sequence[str]],
    *,
    retries: int = 1,
    timeout_seconds: float = 900,
    event_file: str | Path = "data/outputs/pipeline_events.jsonl",
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
    run_id: str | None = None,
) -> dict:
    """Run ordered commands, stopping at the first permanently failed stage.

    Each event is flushed before the next command starts. A failure leaves
    downstream stages untouched. Retry only when the command can be rerun
    safely (e.g., deterministic replacement of its destination).
    """
    if not commands or any(not cmd or any(not isinstance(t, str) or not t for t in cmd)
                           for cmd in commands):
        raise ValueError("At least one nonempty argument-vector command is required")
    if type(retries) is not int or not 0 <= retries <= 10:
        raise ValueError("retries must be an integer from 0 to 10")
    if not 0 < timeout_seconds < float("inf"):
        raise ValueError("timeout_seconds must be finite and positive")

    path = Path(event_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    uid = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    started = time.monotonic()
    events = 0

    def emit(stage: int, attempt: int, status: str, **extra: object) -> None:
        nonlocal events
        payload = {
            "run_id": uid,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "attempt": attempt,
            "status": status,
            **extra,
        }
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(payload, ensure_ascii=True) + "\n")
            out.flush()
        events += 1

    for stage, command in enumerate(commands, 1):
        for attempt in range(1, retries + 2):
            emit(stage, attempt, "started", argv=list(command))
            try:
                result = runner(
                    list(command),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
                returncode = result.returncode
                error = (result.stderr or "")[-1500:]
            except subprocess.TimeoutExpired:
                returncode, error = 124, f"stage exceeded {timeout_seconds}s"
            except OSError as exc:
                returncode, error = 127, str(exc)[-1500:]

            if returncode == 0:
                emit(stage, attempt, "succeeded", returncode=0)
                break

            emit(stage, attempt, "failed", returncode=returncode, error=error)
            if attempt > retries:
                raise PipelineFailure(
                    f"Stage {stage} failed after {attempt} attempt(s): {error}"
                )
            sleeper(min(2 ** (attempt - 1), 30))

    return {
        "run_id": uid,
        "stages_succeeded": len(commands),
        "events_written": events,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "event_file": str(path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/sample_campaign_metrics.csv")
    parser.add_argument("--silver", default="data/silver/campaign_metrics")
    parser.add_argument("--gold", default="data/gold/campaign_performance")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--events", default="data/outputs/pipeline_events.jsonl")
    parser.add_argument("--spark-submit", default="spark-submit")
    args = parser.parse_args(argv)

    commands = [
        [args.spark_submit, STAGES[0], "--input", args.input, "--output", args.silver],
        [args.spark_submit, STAGES[1], "--input", args.silver, "--output", args.gold],
    ]
    try:
        summary = run_pipeline(
            commands,
            retries=args.retries,
            timeout_seconds=args.timeout_seconds,
            event_file=args.events,
        )
    except (PipelineFailure, ValueError) as error:
        print(f"Pipeline failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
