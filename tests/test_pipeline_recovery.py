import unittest

from src.pipeline_recovery import RecoveryNotSafe, plan_recovery


def summary(*statuses):
    return {
        "expected_stages": len(statuses),
        "runs": [{"run_id": "demo", "stages": [
            {"stage": index, "status": status}
            for index, status in enumerate(statuses, 1)
        ]}],
    }


class RecoveryTests(unittest.TestCase):
    def test_failed_first_stage_restarts_from_first(self):
        result = plan_recovery(summary("failed", "not_started"), "demo")
        self.assertEqual(result["restart_at_stage"], 1)

    def test_verified_upstream_can_be_skipped(self):
        result = plan_recovery(summary("succeeded", "failed"), "demo",
                               verified_stage_outputs=[1])
        self.assertEqual(result["restart_at_stage"], 2)
        self.assertEqual(result["skipped_stages"], [1])

    def test_unverified_upstream_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("succeeded", "failed"), "demo")

    def test_running_stage_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("running", "not_started"), "demo")

    def test_stalled_stage_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("stalled", "not_started"), "demo")

    def test_downstream_activity_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("failed", "succeeded"), "demo")

    def test_completed_run_is_noop(self):
        self.assertEqual(plan_recovery(summary("succeeded", "succeeded"), "demo")["action"], "none")

    def test_missing_run_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("failed", "not_started"), "unknown")

    def test_duplicate_run_rejected(self):
        s = summary("failed", "not_started")
        s["runs"].append(s["runs"][0])
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(s, "demo")

    def test_wrong_stage_inventory_rejected(self):
        s = summary("failed", "not_started")
        s["runs"][0]["stages"][1]["stage"] = 3
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(s, "demo")

    def test_unexpected_verified_stage_rejected(self):
        with self.assertRaises(RecoveryNotSafe):
            plan_recovery(summary("succeeded", "failed"), "demo",
                          verified_stage_outputs=[1, 2])

    def test_invalid_verified_list_rejected(self):
        with self.assertRaises(ValueError):
            plan_recovery(summary("failed", "not_started"), "demo",
                          verified_stage_outputs=[True])


if __name__ == "__main__":
    unittest.main()
