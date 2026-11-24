import unittest
from src.reconciliation import reconcile


def row(**changes):
    return dict(platform="search", campaign_id="1", campaign_name="demo",
                impressions=10, clicks=2, spend="0.10", conversions=1,
                revenue="2.00", **{}) | changes


class ReconciliationTests(unittest.TestCase):
    def test_aggregation(self):
        gold = row(impressions=20, clicks=4, spend="0.20", conversions=2, revenue="4")
        self.assertTrue(reconcile([row(), row()], [gold])["passed"])

    def test_count_mismatch(self):
        self.assertEqual(reconcile([row()], [row(clicks=3)])["issues"][0]["metric"], "clicks")

    def test_money_tolerance(self):
        self.assertTrue(reconcile([row()], [row(spend="0.11")])["passed"])
        self.assertFalse(reconcile([row()], [row(spend="0.12")])["passed"])

    def test_missing(self):
        self.assertEqual(reconcile([row()], [])["issues"][0]["issue"], "missing_gold")

    def test_unexpected(self):
        self.assertEqual(reconcile([], [row()])["issues"][0]["issue"], "unexpected_gold")

    def test_duplicate(self):
        with self.assertRaises(ValueError):
            reconcile([row()], [row(), row()])

    def test_invalid_values(self):
        for value in ("NaN", "Infinity", "-1", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reconcile([row(spend=value)], [])

    def test_empty(self):
        self.assertTrue(reconcile([], [])["passed"])

    def test_invalid_key(self):
        with self.assertRaises(ValueError):
            reconcile([row(campaign_id="")], [])
