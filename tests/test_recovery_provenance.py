"""Synthetic local-file regression tests for run-bound recovery evidence."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from src.output_manifest import write_manifest
from src.pipeline_recovery import RecoveryNotSafe
from src.recovery_provenance import plan_with_provenance, record_evidence


def summary():
    return {"expected_stages": 2, "runs": [{
        "run_id": "run-a", "stages": [
            {"stage": 1, "status": "succeeded"},
            {"stage": 2, "status": "failed"},
        ],
    }]}


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.input = root / "input"
        self.output = root / "output"
        self.input.mkdir()
        self.output.mkdir()
        (self.input / "source.csv").write_text("id\n1\n")
        (self.output / "part.csv").write_text("id\n1\n")
        self.im = root / "input-manifest.json"
        self.om = root / "output-manifest.json"
        write_manifest(self.input, self.im)
        write_manifest(self.output, self.om)
        self.paths = {1: (self.output, self.om, self.input, self.im)}
        self.clock = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
        self.evidence = {1: record_evidence(
            run_id="run-a", stage=1, output_dir=self.output,
            output_manifest=self.om, input_dir=self.input,
            input_manifest=self.im, created_at=self.clock,
        )}

    def plan(self, **kwargs):
        return plan_with_provenance(
            summary(), "run-a", self.paths, self.evidence,
            now=self.clock, **kwargs,
        )

    def test_verified_restart(self):
        result = self.plan()
        self.assertEqual(result["restart_at_stage"], 2)
        self.assertEqual(result["provenance_verified_stages"], [1])

    def test_input_mutation_rejected(self):
        (self.input / "source.csv").write_text("id\n2\n")
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_output_mutation_rejected(self):
        (self.output / "part.csv").write_text("id\n2\n")
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_manifest_rewrite_rejected(self):
        data = json.loads(self.im.read_text())
        self.im.write_text(json.dumps(data, indent=4))
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_wrong_run_rejected(self):
        self.evidence[1]["run_id"] = "other-run"
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_wrong_stage_rejected(self):
        self.evidence[1]["stage"] = 2
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_expired_evidence_rejected(self):
        self.clock += timedelta(days=2)
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_future_evidence_rejected(self):
        self.clock -= timedelta(seconds=1)
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_missing_evidence_rejected(self):
        self.evidence.clear()
        with self.assertRaises(RecoveryNotSafe):
            self.plan()

    def test_naive_clock_rejected(self):
        with self.assertRaises(ValueError):
            plan_with_provenance(summary(), "run-a", self.paths,
                                 self.evidence, now=datetime(2026, 11, 19))

    def test_invalid_max_age_rejected(self):
        with self.assertRaises(ValueError):
            self.plan(max_age_seconds=0)

    def test_symlink_input_manifest_rejected(self):
        alias = Path(self.temp.name) / "alias.json"
        alias.symlink_to(self.im)
        self.paths[1] = (self.output, self.om, self.input, alias)
        with self.assertRaises(RecoveryNotSafe):
            self.plan()


if __name__ == "__main__":
    unittest.main()
