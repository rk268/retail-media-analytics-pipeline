"""Conservative restart planning from validated pipeline-monitor summaries.

This module only creates a plan; it never executes Spark or assumes outputs
from a previous run remain valid. Human/operator verification is required.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.pipeline_monitor import summarize_events


class RecoveryNotSafe(ValueError):
    """Event history does not support an unambiguous restart plan."""


def plan_recovery(summary: dict, run_id: str, *, verified_stage_outputs: list[int] | None = None) -> dict:
    """Return a stage-boundary restart plan after explicit artifact verification.

    Only contiguous, successful upstream stages may be skipped. A running or
    stalled stage is never safe to restart until the process is confirmed dead.
    """
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_id is required")
    if not isinstance(summary, dict) or type(summary.get("expected_stages")) is not int:
        raise ValueError("Expected a validated monitor summary")
    total = summary["expected_stages"]
    if total < 1:
        raise ValueError("expected_stages must be positive")
    runs = [r for r in summary.get("runs", []) if r.get("run_id") == run_id]
    if len(runs) != 1:
        raise RecoveryNotSafe("Run ID must uniquely identify an observed run")
    run = runs[0]
    stages = run.get("stages", [])
    if len(stages) != total or [s.get("stage") for s in stages] != list(range(1, total + 1)):
        raise RecoveryNotSafe("Stage inventory is incomplete or inconsistent")
    statuses = [s.get("status") for s in stages]
    if any(s in ("running", "stalled") for s in statuses):
        raise RecoveryNotSafe("Confirm the original process has stopped before planning recovery")
    if any(s not in ("succeeded", "failed", "not_started") for s in statuses):
        raise RecoveryNotSafe("Unrecognized stage state")
    if all(s == "succeeded" for s in statuses):
        return {"run_id": run_id, "action": "none", "reason": "all stages succeeded",
                "restart_at_stage": None, "skipped_stages": []}

    first = next(i for i, status in enumerate(statuses, 1) if status != "succeeded")
    if any(status != "not_started" for status in statuses[first:]):
        raise RecoveryNotSafe("Downstream stages have activity after the restart boundary")
    upstream = list(range(1, first))
    verified = verified_stage_outputs if verified_stage_outputs is not None else []
    if (not isinstance(verified, list) or any(type(n) is not int for n in verified)
            or len(set(verified)) != len(verified)):
        raise ValueError("verified_stage_outputs must be a list of distinct integer stage numbers")
    if sorted(verified) != upstream:
        raise RecoveryNotSafe("Every skipped upstream output must be explicitly verified")
    return {
        "run_id": run_id,
        "action": "manual_restart",
        "restart_at_stage": first,
        "skipped_stages": upstream,
        "reason": "upstream stages succeeded and their artifacts were explicitly verified",
        "caution": "Check idempotency, input snapshot, output partitions and lock ownership before rerunning",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-stages", type=int, default=2)
    parser.add_argument("--verified-stage", action="append", type=int, default=[])
    args = parser.parse_args()
    try:
        summary = summarize_events(args.events, expected_stages=args.expected_stages)
        result = plan_recovery(summary, args.run_id, verified_stage_outputs=args.verified_stage)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Recovery planning refused: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
