"""Isolated orchestration tests; no Spark installation needed."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.pipeline_orchestrator import PipelineFailure, run_pipeline


class PipelineOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.events = Path(self.temp.name) / "events.jsonl"
        self.commands = [["spark-submit", "silver.py"], ["spark-submit", "gold.py"]]

    def records(self):
        return [json.loads(line) for line in self.events.read_text().splitlines()]

    def test_success_runs_in_order(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        summary = run_pipeline(self.commands, runner=runner, event_file=self.events)
        self.assertEqual(summary["stages_succeeded"], 2)
        self.assertEqual([r["status"] for r in self.records()],
                         ["started", "succeeded", "started", "succeeded"])
        self.assertEqual([c.args[0] for c in runner.call_args_list], self.commands)

    def test_retry_then_success(self):
        runner = Mock(side_effect=[
            subprocess.CompletedProcess([], 1, "", "temporary"),
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ])
        run_pipeline(self.commands, retries=1, runner=runner, sleeper=lambda _: None,
                     event_file=self.events)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual([r["status"] for r in self.records()],
                         ["started", "failed", "started", "succeeded", "started", "succeeded"])

    def test_stop_before_downstream_on_failure(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 2, "", "broken"))
        with self.assertRaises(PipelineFailure):
            run_pipeline(self.commands, retries=0, runner=runner, event_file=self.events)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual([r["stage"] for r in self.records()], [1, 1])

    def test_timeout_is_logged(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired(["spark-submit"], 1))
        with self.assertRaises(PipelineFailure):
            run_pipeline(self.commands, retries=0, runner=runner, event_file=self.events)
        self.assertEqual(self.records()[-1]["returncode"], 124)

    def test_missing_executable_is_logged(self):
        runner = Mock(side_effect=FileNotFoundError("spark-submit"))
        with self.assertRaises(PipelineFailure):
            run_pipeline(self.commands, retries=0, runner=runner, event_file=self.events)
        self.assertEqual(self.records()[-1]["returncode"], 127)

    def test_invalid_retry_configuration(self):
        for retries in (-1, 11, 1.5, True):
            with self.subTest(retries=retries), self.assertRaises(ValueError):
                run_pipeline(self.commands, retries=retries, event_file=self.events)

    def test_invalid_commands(self):
        for commands in ([], [[]], [[""]]):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                run_pipeline(commands, event_file=self.events)

    def test_invalid_timeout(self):
        for timeout in (0, float("inf"), -1):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                run_pipeline(self.commands, timeout_seconds=timeout, event_file=self.events)

    def test_events_include_run_id(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        run_pipeline(self.commands[:1], runner=runner, run_id="demo-123", event_file=self.events)
        self.assertTrue(all(r["run_id"] == "demo-123" for r in self.records()))

    def test_no_shell_interpolation(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        run_pipeline([["echo", "hello; touch bad"]], runner=runner, event_file=self.events)
        kwargs = runner.call_args.kwargs
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(runner.call_args.args[0][1], "hello; touch bad")


if __name__ == "__main__":
    unittest.main()
