"""SQLite executable contract tests for last-touch attribution SQL."""
import sqlite3
import unittest
from pathlib import Path

SQL = (Path(__file__).resolve().parents[1] / "sql" / "last_touch_attribution.sql").read_text()


class LastTouchAttributionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE orders (
              order_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
              order_ts TEXT NOT NULL, revenue REAL NOT NULL
            );
            CREATE TABLE ad_touches (
              touch_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL,
              touch_ts TEXT NOT NULL, channel TEXT NOT NULL,
              campaign_id TEXT NOT NULL
            );
        """)

    def run_model(self):
        return self.db.execute(SQL).fetchall()

    def test_latest_eligible_touch_wins(self):
        self.db.executemany("INSERT INTO ad_touches VALUES (?,?,?,?,?)", [
            ("a", "u1", "2026-01-02 10:00:00", "search", "s1"),
            ("b", "u1", "2026-01-03 10:00:00", "social", "m1"),
        ])
        self.db.execute("INSERT INTO orders VALUES (?,?,?,?)",
                        ("o1", "u1", "2026-01-04 10:00:00", 80))
        self.assertEqual(self.run_model(), [("social", "m1", 1, 80.0)])

    def test_future_touch_and_old_touch_excluded(self):
        self.db.executemany("INSERT INTO ad_touches VALUES (?,?,?,?,?)", [
            ("old", "u1", "2026-01-01 00:00:00", "search", "s1"),
            ("future", "u1", "2026-01-12 00:00:00", "social", "m1"),
        ])
        self.db.execute("INSERT INTO orders VALUES (?,?,?,?)",
                        ("o1", "u1", "2026-01-10 00:00:00", 50))
        self.assertEqual(self.run_model(), [])

    def test_exact_seven_day_boundary_is_included(self):
        self.db.execute("INSERT INTO ad_touches VALUES (?,?,?,?,?)",
                        ("t", "u", "2026-01-01 00:00:00", "search", "s"))
        self.db.execute("INSERT INTO orders VALUES (?,?,?,?)",
                        ("o", "u", "2026-01-08 00:00:00", 20))
        self.assertEqual(self.run_model(), [("search", "s", 1, 20.0)])

    def test_tie_breaks_by_touch_id(self):
        self.db.executemany("INSERT INTO ad_touches VALUES (?,?,?,?,?)", [
            ("a", "u", "2026-01-03 00:00:00", "search", "s"),
            ("b", "u", "2026-01-03 00:00:00", "social", "m"),
        ])
        self.db.execute("INSERT INTO orders VALUES (?,?,?,?)",
                        ("o", "u", "2026-01-04 00:00:00", 25))
        self.assertEqual(self.run_model(), [("social", "m", 1, 25.0)])

    def test_multiple_orders_are_not_deduplicated_by_customer(self):
        self.db.execute("INSERT INTO ad_touches VALUES (?,?,?,?,?)",
                        ("t", "u", "2026-01-03 00:00:00", "search", "s"))
        self.db.executemany("INSERT INTO orders VALUES (?,?,?,?)", [
            ("o1", "u", "2026-01-04 00:00:00", 10),
            ("o2", "u", "2026-01-05 00:00:00", 15),
        ])
        self.assertEqual(self.run_model(), [("search", "s", 2, 25.0)])

    def test_unmatched_customer_does_not_attribute(self):
        self.db.execute("INSERT INTO ad_touches VALUES (?,?,?,?,?)",
                        ("t", "other", "2026-01-03 00:00:00", "search", "s"))
        self.db.execute("INSERT INTO orders VALUES (?,?,?,?)",
                        ("o", "u", "2026-01-04 00:00:00", 10))
        self.assertEqual(self.run_model(), [])


if __name__ == "__main__":
    unittest.main()
