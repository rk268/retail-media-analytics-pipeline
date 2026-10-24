"""Strict adapters for *fictional* Google/Meta-like daily campaign exports.

Outputs the canonical CSV consumed by bronze_to_silver.py. This is a
portfolio demonstration, not a client integration or a vendor API contract.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import os
from pathlib import Path
import re
import tempfile

CANONICAL = (
    "event_date", "platform", "campaign_id", "campaign_name",
    "impressions", "clicks", "spend", "conversions", "revenue",
)
SOURCES = {
    "google_ads": {
        "event_date": "date", "campaign_id": "campaign_id",
        "campaign_name": "campaign_name", "impressions": "impressions",
        "clicks": "clicks", "spend": "cost_micros",
        "conversions": "conversions", "revenue": "conversion_value_usd",
    },
    "meta_ads": {
        "event_date": "day", "campaign_id": "ad_campaign_id",
        "campaign_name": "ad_campaign_name", "impressions": "views",
        "clicks": "link_clicks", "spend": "spend_usd",
        "conversions": "purchases", "revenue": "purchase_value_usd",
    },
}


def _count(value: str, field: str) -> int:
    if not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError(f"{field} must be a nonnegative integer")
    return int(value)


def _money(value: str, field: str, *, micros: bool = False) -> str:
    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    if micros:
        _count(value, field)  # mock cost_micros is integer micro-USD
        amount /= Decimal(1_000_000)
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def adapt_row(source: str, row: dict[str, str]) -> dict[str, str]:
    """Normalize one row; fail closed on invalid dates, keys or metrics."""
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source}")
    m = SOURCES[source]
    missing = set(m.values()) - row.keys()
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    day = row[m["event_date"]].strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Date must use YYYY-MM-DD")
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("Invalid calendar date") from exc
    campaign_id = row[m["campaign_id"]].strip()
    campaign_name = row[m["campaign_name"]].strip()
    if not campaign_id or not campaign_name:
        raise ValueError("Campaign ID and name must be nonempty")
    impressions = _count(row[m["impressions"]], "impressions")
    clicks = _count(row[m["clicks"]], "clicks")
    conversions = _count(row[m["conversions"]], "conversions")
    if clicks > impressions:
        raise ValueError("Clicks cannot exceed impressions in this demo")
    return {
        "event_date": day, "platform": source,
        "campaign_id": campaign_id, "campaign_name": campaign_name,
        "impressions": str(impressions), "clicks": str(clicks),
        "spend": _money(row[m["spend"]], "spend", micros=source == "google_ads"),
        "conversions": str(conversions),
        "revenue": _money(row[m["revenue"]], "revenue"),
    }


def normalize_files(inputs: dict[str, str | Path], output: str | Path) -> int:
    """Validate *all* files before atomically replacing the output CSV."""
    if not inputs or set(inputs) - SOURCES.keys():
        raise ValueError("Specify at least one supported source")
    output = Path(output)
    if any(Path(p).resolve() == output.resolve() for p in inputs.values()):
        raise ValueError("Output must differ from source files")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source, path in sorted(inputs.items()):
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            if len(headers) != len(set(headers)):
                raise ValueError(f"{source}: duplicate CSV headers")
            missing = set(SOURCES[source].values()) - set(headers)
            if missing:
                raise ValueError(f"{source}: missing columns {sorted(missing)}")
            for line_number, raw in enumerate(reader, start=2):
                if None in raw:
                    raise ValueError(f"{source} line {line_number}: extra CSV columns")
                try:
                    record = adapt_row(source, raw)
                except (ValueError, AttributeError) as exc:
                    raise ValueError(f"{source} line {line_number}: {exc}") from exc
                key = (record["event_date"], source, record["campaign_id"])
                if key in seen:
                    raise ValueError(f"{source} line {line_number}: duplicate campaign-day {key}")
                seen.add(key)
                normalized.append(record)
    if not normalized:
        raise ValueError("No data rows to normalize")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", newline="", encoding="utf-8", dir=output.parent,
            prefix=".adapters-", suffix=".tmp", delete=False,
        ) as handle:
            temp_name = handle.name
            writer = csv.DictWriter(handle, fieldnames=CANONICAL, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sorted(normalized, key=lambda r: (
                r["event_date"], r["platform"], r["campaign_id"])))
        os.replace(temp_name, output)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return len(normalized)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--google", help="CSV in fictional Google-like schema")
    parser.add_argument("--meta", help="CSV in fictional Meta-like schema")
    parser.add_argument("--output", required=True, help="Canonical CSV output")
    args = parser.parse_args()
    inputs = {k: p for k, p in (("google_ads", args.google), ("meta_ads", args.meta)) if p}
    print(f"Normalized {normalize_files(inputs, args.output)} campaign-day records")


if __name__ == "__main__":
    main()
