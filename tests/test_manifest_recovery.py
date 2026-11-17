"""Manifest-gated recovery integration tests using synthetic files."""
import json
import tempfile
import unittest
from pathlib import Path

from src.output_manifest import write_manifest
from src.pipeline_recovery import RecoveryNotSafe
from src.manifest_recovery import plan_manifest_gated_recovery


def summary(*statuses):
    return {"expected_stages": len(statuses), "runs": [{
        "run_id": "synthetic-run",
        "stages": [{"stage": i, "status": status} for i, status in enumerate(statuses, 1)],
    }]}


class ManifestRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.output = root / "silver"
        self.output.mkdir()
        self.data = self.output / "part-000.csv"
        self.data.write_text("campaign,clicks\na,3\n", encoding="utf-8")
        self.manifest = root / "silver-manifest.json"
        write_manifest(self.output, self.manifest)
        self.artifacts = {1: (self.output, self.manifest)}

    def plan(self, statuses, artifacts=None):
        return plan_manifest_gated_recovery(
            summary(*statuses), "synthetic-run",
            self.artifacts if artifacts is None else artifacts,
        )

    def test_valid_manifest_allows_second_stage_restart(self):
        result = self.plan(("succeeded", "failed"))
        self.assertEqual(result["restart_at_stage"], 2)
        self.assertEqual(result["skipped_stages"], [1])

    def test_modified_output_refused(self):
        self.data.write_text("tampered", encoding="utf-8")
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"))

    def test_missing_output_refused(self):
        self.data.unlink()
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"))

    def test_added_output_refused(self):
        (self.output / "extra.csv").write_text("extra", encoding="utf-8")
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"))

    def test_missing_manifest_refused(self):
        self.manifest.unlink()
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"))

    def test_invalid_manifest_json_refused(self):
        self.manifest.write_text("{", encoding="utf-8")
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"))

    def test_no_manifest_for_skipped_stage_refused(self):
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"), {})

    def test_failed_first_stage_requires_no_manifest(self):
        result = self.plan(("failed", "not_started"), {})
        self.assertEqual(result["restart_at_stage"], 1)

    def test_complete_run_is_noop(self):
        self.assertEqual(self.plan(("succeeded", "succeeded"), {})["action"], "none")

    def test_running_stage_refused(self):
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("running", "not_started"), {})

    def test_symlink_manifest_refused(self):
        alias = Path(self.temp.name) / "alias.json"
        alias.symlink_to(self.manifest)
        with self.assertRaises(RecoveryNotSafe):
            self.plan(("succeeded", "failed"), {1: (self.output, alias)})


if __name__ == "__main__":
    unittest.main()
