"""Operational health summaries for the local retail-media pipeline.

Consumes the JSONL event contract emitted by src.pipeline_orchestrator.
Pure Python; suitable for monitoring dashboards without Spark.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any, Sequence


STATUSES = ("succeeded", "failed", "running", "stalled", "incomplete")


def _timestamp(value: Any, line: int) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"Line {line}: timestamp_utc must be a string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Line {line}: invalid timestamp_utc") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Line {line}: timestamp_utc must include a timezone")
    return parsed.astimezone(timezone.utc)


def summarize_events(
    event_file: str | Path,
    *,
    expected_stages: int = 2,
    stale_after_seconds: float = 600,
    now: datetime | None = None,
) -> dict:
    """Validate event ordering and build per-run, per-stage health records.

    A terminal failure is a snapshot state: the producer may later append a
    retry. An unfinished attempt becomes stalled after the configured age.
    """
    if type(expected_stages) is not int or expected_stages < 1:
        raise ValueError("expected_stages must be a positive integer")
    if not isinstance(stale_after_seconds, (int, float)) or (
        not math.isfinite(stale_after_seconds) or stale_after_seconds <= 0
    ):
        raise ValueError("stale_after_seconds must be finite and positive")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include a timezone")
    current = current.astimezone(timezone.utc)

    runs: dict[str, dict] = {}
    with Path(event_file).open("r", encoding="utf-8") as stream:
        for line_no, raw in enumerate(stream, 1):
            if not raw.strip():
                continue
            try:
                event = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {line_no}: invalid JSON") from exc
            if not isinstance(event, dict):
                raise ValueError(f"Line {line_no}: expected a JSON object")

            uid = event.get("run_id")
            stage = event.get("stage")
            attempt = event.get("attempt")
            status = event.get("status")
            if not isinstance(uid, str) or not uid.strip():
                raise ValueError(f"Line {line_no}: invalid run_id")
            if type(stage) is not int or not 1 <= stage <= expected_stages:
                raise ValueError(f"Line {line_no}: stage outside expected range")
            if type(attempt) is not int or attempt < 1:
                raise ValueError(f"Line {line_no}: invalid attempt")
            if status not in ("started", "succeeded", "failed"):
                raise ValueError(f"Line {line_no}: invalid status")
            ts = _timestamp(event.get("timestamp_utc"), line_no)
            record = runs.setdefault(uid, {"first": ts, "last": ts, "stages": {}})
            if ts < record["last"]:
                raise ValueError(f"Line {line_no}: run events are not chronological")
            record["last"] = ts
            stage_attempts = record["stages"].setdefault(stage, {})

            if status == "started":
                if attempt in stage_attempts:
                    raise ValueError(f"Line {line_no}: duplicate attempt start")
                if attempt != len(stage_attempts) + 1:
                    raise ValueError(f"Line {line_no}: non-sequential attempt")
                if attempt > 1 and stage_attempts[attempt - 1]["status"] != "failed":
                    raise ValueError(f"Line {line_no}: retry requires failed attempt")
                if stage > 1:
                    previous = record["stages"].get(stage - 1, {})
                    if not previous or list(previous.values())[-1]["status"] != "succeeded":
                        raise ValueError(f"Line {line_no}: previous stage not successful")
                stage_attempts[attempt] = {
                    "started": ts,
                    "finished": None,
                    "status": "running",
                    "error": None,
                }
            else:
                item = stage_attempts.get(attempt)
                if item is None or item["status"] != "running":
                    raise ValueError(f"Line {line_no}: terminal event without active attempt")
                returncode = event.get("returncode")
                if type(returncode) is not int or (
                    status == "succeeded" and returncode != 0
                ) or (status == "failed" and returncode == 0):
                    raise ValueError(f"Line {line_no}: status/returncode mismatch")
                item["status"] = status
                item["finished"] = ts
                item["error"] = str(event.get("error", ""))[-500:] if status == "failed" else None

    summaries = []
    for uid, record in runs.items():
        stage_summaries = []
        for stage in range(1, expected_stages + 1):
            attempts = record["stages"].get(stage, {})
            if not attempts:
                stage_status = "not_started"
            else:
                last = attempts[max(attempts)]
                stage_status = last["status"]
                if stage_status == "running" and (
                    current - last["started"]
                ).total_seconds() > stale_after_seconds:
                    stage_status = "stalled"
            last_error = next(
                (a["error"] for a in reversed(list(attempts.values())) if a["error"]),
                None,
            )
            stage_summaries.append({
                "stage": stage,
                "status": stage_status,
                "attempts": len(attempts),
                "retries": max(0, len(attempts) - 1),
                "failed_attempts": sum(a["status"] == "failed" for a in attempts.values()),
                "last_error": last_error,
            })
        states = [s["status"] for s in stage_summaries]
        if all(s == "succeeded" for s in states):
            state = "succeeded"
        elif "failed" in states:
            state = "failed"
        elif "stalled" in states:
            state = "stalled"
        elif "running" in states:
            state = "running"
        else:
            state = "incomplete"
        summaries.append({
            "run_id": uid,
            "status": state,
            "first_event_utc": record["first"].isoformat(),
            "last_event_utc": record["last"].isoformat(),
            "observed_duration_seconds": round(
                (record["last"] - record["first"]).total_seconds(), 3
            ),
            "retries": sum(s["retries"] for s in stage_summaries),
            "stages": stage_summaries,
        })
    summaries.sort(key=lambda r: (r["last_event_utc"], r["run_id"]), reverse=True)
    counts = Counter(r["status"] for r in summaries)
    return {
        "schema_version": 1,
        "generated_at_utc": current.isoformat(),
        "expected_stages": expected_stages,
        "stale_after_seconds": stale_after_seconds,
        "run_count": len(summaries),
        "latest_run_id": summaries[0]["run_id"] if summaries else None,
        "health_counts": {s: counts[s] for s in STATUSES},
        "runs": summaries,
    }


def write_summary(summary: dict, output_path: str | Path) -> None:
    """Atomically replace dashboard JSON only after successful validation."""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=f".{target.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            json.dump(summary, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default="data/outputs/pipeline_events.jsonl")
    parser.add_argument("--output", default="data/outputs/pipeline_health.json")
    parser.add_argument("--expected-stages", type=int, default=2)
    parser.add_argument("--stale-after-seconds", type=float, default=600)
    parser.add_argument("--fail-on-unhealthy", action="store_true")
    args = parser.parse_args(argv)
    if Path(args.events).resolve() == Path(args.output).resolve():
        parser.error("--events and --output must be different files")
    try:
        result = summarize_events(
            args.events,
            expected_stages=args.expected_stages,
            stale_after_seconds=args.stale_after_seconds,
        )
        write_summary(result, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Monitoring failed: {exc}\n")
    print(json.dumps({
        "latest_run_id": result["latest_run_id"],
        "run_count": result["run_count"],
        "health_counts": result["health_counts"],
        "output": args.output,
    }))
    return int(args.fail_on_unhealthy and (
        result["run_count"] == 0 or
        result["health_counts"]["succeeded"] != result["run_count"]
    ))


if __name__ == "__main__":
    raise SystemExit(main())
