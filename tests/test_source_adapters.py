"""Unit and file-level tests for simulated platform source adapters."""
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.source_adapters import CANONICAL, adapt_row, normalize_files


GOOGLE = {
    "date": "2026-10-01", "campaign_id": "G1", "campaign_name": "Demo Search",
    "impressions": "100", "clicks": "10", "cost_micros": "1234567",
    "conversions": "2", "conversion_value_usd": "25.125",
}
META = {
    "day": "2026-10-01", "ad_campaign_id": "M1", "ad_campaign_name": "Demo Social",
    "views": "200", "link_clicks": "12", "spend_usd": "7.995",
    "purchases": "1", "purchase_value_usd": "18.00",
}


class AdapterTests(unittest.TestCase):
    def test_google_micros_and_currency_rounding(self):
        row = adapt_row("google_ads", GOOGLE)
        self.assertEqual(row["spend"], "1.23")
        self.assertEqual(row["revenue"], "25.13")
        self.assertEqual(row["platform"], "google_ads")

    def test_meta_field_mapping(self):
        row = adapt_row("meta_ads", META)
        self.assertEqual((row["impressions"], row["clicks"], row["spend"]),
                         ("200", "12", "8.00"))

    def test_rejects_bad_dates(self):
        for day in ("2026-02-30", "20261001", "2026-1-1"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                adapt_row("google_ads", {**GOOGLE, "date": day})

    def test_rejects_invalid_metrics(self):
        for field, value in (("impressions", "-1"), ("clicks", "101"),
                             ("conversions", "2.5"), ("cost_micros", "1.5"),
                             ("conversion_value_usd", "NaN"),
                             ("conversion_value_usd", "-5")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                adapt_row("google_ads", {**GOOGLE, field: value})

    def test_rejects_missing_required_column(self):
        with self.assertRaisesRegex(ValueError, "Missing columns"):
            adapt_row("meta_ads", {k: v for k, v in META.items() if k != "views"})

    def _write(self, path, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def test_multi_source_canonical_csv(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            google, meta, output = root / "g.csv", root / "m.csv", root / "out.csv"
            self._write(google, [GOOGLE])
            self._write(meta, [META])
            self.assertEqual(normalize_files({"google_ads": google, "meta_ads": meta}, output), 2)
            with output.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(tuple(reader.fieldnames), CANONICAL)
                rows = list(reader)
            self.assertEqual({r["platform"] for r in rows}, {"google_ads", "meta_ads"})

    def test_duplicate_campaign_day_rejected_without_overwriting_output(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "g.csv", root / "out.csv"
            self._write(source, [GOOGLE, GOOGLE])
            output.write_text("previous output", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate campaign-day"):
                normalize_files({"google_ads": source}, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous output")

    def test_empty_input_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "g.csv", root / "out.csv"
            self._write(source, [GOOGLE])
            source.write_text(source.read_text(encoding="utf-8").splitlines()[0] + "\n")
            with self.assertRaisesRegex(ValueError, "No data rows"):
                normalize_files({"google_ads": source}, output)
            self.assertFalse(output.exists())

    def test_output_must_not_clobber_input(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "g.csv"
            self._write(path, [GOOGLE])
            with self.assertRaisesRegex(ValueError, "Output must differ"):
                normalize_files({"google_ads": path}, path)

    def test_duplicate_headers_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "g.csv"
            path.write_text("date,date,campaign_id\n2026-10-01,2026-10-01,G1\n")
            with self.assertRaisesRegex(ValueError, "duplicate CSV headers"):
                normalize_files({"google_ads": path}, Path(directory) / "out.csv")


if __name__ == "__main__":
    unittest.main()
