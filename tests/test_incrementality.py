"""Tests for synthetic incrementality calculations and input validation."""
import tempfile
import unittest
from pathlib import Path
from src.incrementality import analyze, read_cohorts


class IncrementalityTests(unittest.TestCase):
    def setUp(self):
        self.cohorts = {
            "treatment": dict(users=50000, conversions=3000, revenue=240000.0, spend=45000.0),
            "control": dict(users=50000, conversions=2600, revenue=208000.0, spend=0.0),
        }

    def test_lift_and_revenue(self):
        metrics = analyze(self.cohorts)
        self.assertAlmostEqual(metrics["absolute_conversion_rate_lift"], 0.008)
        self.assertAlmostEqual(metrics["incremental_conversions_at_treatment_scale"], 400)
        self.assertAlmostEqual(metrics["incremental_revenue_at_treatment_scale"], 32000)
        self.assertAlmostEqual(metrics["incremental_roas"], 32000 / 45000)
        lo, hi = metrics["conversion_rate_difference_95pct_wald_ci"]
        self.assertLess(lo, 0.008)
        self.assertGreater(hi, 0.008)

    def test_zero_control_rate(self):
        self.cohorts["control"]["conversions"] = 0
        self.assertIsNone(analyze(self.cohorts)["relative_conversion_rate_lift"])

    def test_zero_incremental_spend(self):
        self.cohorts["control"]["spend"] = 45000
        self.assertIsNone(analyze(self.cohorts)["incremental_roas"])

    def test_invalid_count(self):
        self.cohorts["treatment"]["conversions"] = 60000
        with self.assertRaises(ValueError):
            analyze(self.cohorts)

    def test_missing_control(self):
        del self.cohorts["control"]
        with self.assertRaises(ValueError):
            analyze(self.cohorts)

    def test_parser_rejects_duplicate_arm(self):
        self.assert_csv_invalid("group,users,conversions,revenue,spend\ntreatment,10,1,1,1\ntreatment,10,1,1,1\n")

    def test_parser_rejects_nonfinite_money(self):
        self.assert_csv_invalid("group,users,conversions,revenue,spend\ntreatment,10,1,nan,1\ncontrol,10,1,1,0\n")

    def assert_csv_invalid(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohorts.csv"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                read_cohorts(path)


if __name__ == "__main__":
    unittest.main()
