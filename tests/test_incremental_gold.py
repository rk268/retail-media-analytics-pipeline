"""Synthetic Spark regression tests for date-scoped Gold publication."""
from datetime import date

import pytest
from pyspark.sql import SparkSession, functions as F

from src.incremental_gold import build_daily_gold, parse_day, write_daily_partition


SCHEMA = (
    "event_date date, platform string, campaign_id string, campaign_name string, "
    "impressions long, clicks long, spend double, conversions long, revenue double"
)


@pytest.fixture(scope="module")
def spark():
    session = (SparkSession.builder.master("local[1]")
               .appName("incremental-gold-tests")
               .config("spark.ui.enabled", "false").getOrCreate())
    yield session
    session.stop()


def row(day, impressions=100, clicks=10, spend=20.0, conversions=2, revenue=60.0):
    return (date.fromisoformat(day), "google_ads", "campaign-1", "Synthetic Campaign",
            impressions, clicks, spend, conversions, revenue)


def test_strict_partition_date():
    assert parse_day("2026-10-25") == date(2026, 10, 25)
    for invalid in ("2026-2-01", "2026-02-30", "2026-10-01T00:00", "", None):
        with pytest.raises(ValueError):
            parse_day(invalid)


def test_build_daily_gold_keeps_date_grain_and_kpis(spark):
    silver = spark.createDataFrame([row("2026-10-01"), row("2026-10-02", 200, 20, 40.0, 4, 100.0)], SCHEMA)
    daily = build_daily_gold(silver, "2026-10-01").collect()
    assert len(daily) == 1
    metrics = daily[0].asDict()
    assert metrics["event_date"] == date(2026, 10, 1)
    assert metrics["impressions"] == 100
    assert metrics["ctr"] == pytest.approx(0.1)
    assert metrics["roas"] == pytest.approx(3.0)


def test_rejects_empty_target_day(spark):
    silver = spark.createDataFrame([row("2026-10-01")], SCHEMA)
    with pytest.raises(ValueError, match="No Silver records"):
        build_daily_gold(silver, "2026-10-03")


def test_rejects_duplicate_campaign_day(spark):
    silver = spark.createDataFrame([row("2026-10-01"), row("2026-10-01")], SCHEMA)
    with pytest.raises(ValueError, match="Duplicate"):
        build_daily_gold(silver, "2026-10-01")


def test_rejects_nonfinite_money(spark):
    silver = spark.createDataFrame([row("2026-10-01", spend=float("nan"))], SCHEMA)
    with pytest.raises(ValueError, match="nonfinite"):
        build_daily_gold(silver, "2026-10-01")


def test_dynamic_overwrite_is_idempotent_and_preserves_other_day(spark, tmp_path):
    path = str(tmp_path / "daily_gold")
    silver = spark.createDataFrame([row("2026-10-01"), row("2026-10-02")], SCHEMA)
    for day in ("2026-10-01", "2026-10-02"):
        write_daily_partition(build_daily_gold(silver, day), path)
    updated = spark.createDataFrame([row("2026-10-01", impressions=300, clicks=30)], SCHEMA)
    write_daily_partition(build_daily_gold(updated, "2026-10-01"), path)
    write_daily_partition(build_daily_gold(updated, "2026-10-01"), path)
    by_date = {r["event_date"]: r for r in spark.read.parquet(path).collect()}
    assert len(by_date) == 2
    assert by_date[date(2026, 10, 1)]["impressions"] == 300
    assert by_date[date(2026, 10, 2)]["impressions"] == 100


def test_rejects_empty_gold_write(spark, tmp_path):
    gold = build_daily_gold(spark.createDataFrame([row("2026-10-01")], SCHEMA), "2026-10-01")
    with pytest.raises(ValueError, match="exactly one"):
        write_daily_partition(gold.where(F.lit(False)), str(tmp_path / "empty"))
