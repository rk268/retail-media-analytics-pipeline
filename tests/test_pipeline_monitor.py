"""Deterministic operational-monitoring regression tests; no Spark required."""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest

from src.pipeline_monitor import main, summarize_events, write_summary


NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.events = Path(self.temp.name) / "events.jsonl"
        self.output = Path(self.temp.name) / "health.json"
        self.rows = []

    def add(self, uid="run-a", stage=1, attempt=1, status="started",
            seconds=-100, returncode=None, error=None):
        event = {
            "run_id": uid,
            "stage": stage,
            "attempt": attempt,
            "status": status,
            "timestamp_utc": (NOW + timedelta(seconds=seconds)).isoformat(),
        }
        if returncode is not None:
            event["returncode"] = returncode
        if error is not None:
            event["error"] = error
        self.rows.append(event)

    def save(self):
        self.events.write_text(
            "".join(json.dumps(row) + "\n" for row in self.rows),
            encoding="utf-8",
        )

    def report(self, **kwargs):
        self.save()
        return summarize_events(self.events, now=NOW, **kwargs)

    def test_successful_two_stage_run(self):
        self.add(seconds=-50)
        self.add(status="succeeded", seconds=-45, returncode=0)
        self.add(stage=2, seconds=-44)
        self.add(stage=2, status="succeeded", seconds=-40, returncode=0)
        summary = self.report()
        self.assertEqual(summary["health_counts"]["succeeded"], 1)
        self.assertEqual(summary["latest_run_id"], "run-a")
        self.assertEqual(summary["runs"][0]["observed_duration_seconds"], 10)
        self.assertEqual([s["status"] for s in summary["runs"][0]["stages"]],
                         ["succeeded", "succeeded"])

    def test_failed_stage_blocks_success(self):
        self.add()
        self.add(status="failed", seconds=-99, returncode=2, error="bad input")
        result = self.report()
        self.assertEqual(result["runs"][0]["status"], "failed")
        self.assertEqual(result["runs"][0]["stages"][0]["last_error"], "bad input")
        self.assertEqual(result["runs"][0]["stages"][1]["status"], "not_started")

    def test_retry_then_success(self):
        self.add()
        self.add(status="failed", seconds=-99, returncode=1, error="temporary")
        self.add(attempt=2, seconds=-98)
        self.add(attempt=2, status="succeeded", seconds=-97, returncode=0)
        self.add(stage=2, seconds=-96)
        self.add(stage=2, status="succeeded", seconds=-95, returncode=0)
        result = self.report()["runs"][0]
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["retries"], 1)
        self.assertEqual(result["stages"][0]["failed_attempts"], 1)

    def test_running_not_yet_stale(self):
        self.add(seconds=-30)
        self.assertEqual(self.report(stale_after_seconds=60)["runs"][0]["status"],
                         "running")

    def test_stalled_stage(self):
        self.add(seconds=-90)
        self.assertEqual(self.report(stale_after_seconds=60)["runs"][0]["status"],
                         "stalled")

    def test_finished_old_run_not_stalled(self):
        self.add(seconds=-10000)
        self.add(status="succeeded", seconds=-9999, returncode=0)
        self.add(stage=2, seconds=-9998)
        self.add(stage=2, status="succeeded", seconds=-9997, returncode=0)
        self.assertEqual(self.report()["runs"][0]["status"], "succeeded")

    def test_multiple_runs_sorted_by_last_event(self):
        self.add(uid="old", seconds=-50)
        self.add(uid="old", status="failed", seconds=-40, returncode=1)
        self.add(uid="new", seconds=-20)
        summary = self.report()
        self.assertEqual(summary["latest_run_id"], "new")
        self.assertEqual(summary["run_count"], 2)

    def test_empty_log_is_not_success(self):
        summary = self.report()
        self.assertEqual(summary["run_count"], 0)
        self.assertIsNone(summary["latest_run_id"])

    def test_invalid_json(self):
        self.events.write_text("{oops\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Line 1"):
            summarize_events(self.events, now=NOW)

    def test_invalid_timezone(self):
        self.add()
        self.rows[0]["timestamp_utc"] = "2026-10-31T11:00:00"
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.report()

    def test_orphan_terminal_rejected(self):
        self.add(status="succeeded", returncode=0)
        with self.assertRaisesRegex(ValueError, "without active"):
            self.report()

    def test_duplicate_start_rejected(self):
        self.add()
        self.add(seconds=-99)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.report()

    def test_wrong_returncode_rejected(self):
        self.add()
        self.add(status="succeeded", seconds=-99, returncode=1)
        with self.assertRaisesRegex(ValueError, "returncode"):
            self.report()

    def test_skipped_stage_rejected(self):
        self.add(stage=2)
        with self.assertRaisesRegex(ValueError, "previous stage"):
            self.report()

    def test_retry_requires_failure(self):
        self.add()
        self.add(attempt=2, seconds=-99)
        with self.assertRaisesRegex(ValueError, "retry requires"):
            self.report()

    def test_event_timestamp_order_rejected(self):
        self.add(seconds=-90)
        self.add(status="succeeded", seconds=-100, returncode=0)
        with self.assertRaisesRegex(ValueError, "chronological"):
            self.report()

    def test_invalid_configuration(self):
        self.save()
        for kwargs in ({"expected_stages": 0},
                       {"stale_after_seconds": 0},
                       {"stale_after_seconds": float("nan")},
                       {"now": datetime(2026, 10, 31)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                summarize_events(self.events, **kwargs)

    def test_atomic_output_round_trip(self):
        self.add()
        self.add(status="failed", seconds=-99, returncode=2)
        summary = self.report()
        write_summary(summary, self.output)
        self.assertEqual(json.loads(self.output.read_text()), summary)
        self.assertEqual(list(Path(self.temp.name).glob("*.tmp")), [])

    def test_cli_unhealthy_exit_and_output(self):
        self.add()
        self.add(status="failed", seconds=-99, returncode=2)
        self.save()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = main(["--events", str(self.events), "--output", str(self.output),
                       "--fail-on-unhealthy"])
        self.assertEqual(rc, 1)
        self.assertTrue(self.output.exists())


if __name__ == "__main__":
    unittest.main()
