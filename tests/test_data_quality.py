"""Spark quality-gate tests using synthetic campaign observations."""
import pytest
from pyspark.sql import SparkSession
from src.data_quality import assert_quality, quality_report


@pytest.fixture(scope="module")
def spark():
    session = SparkSession.builder.master("local[1]").appName("quality-tests").getOrCreate()
    yield session
    session.stop()


def rows(spark, values):
    schema = "event_date string, platform string, campaign_id string, impressions long, clicks long, spend double, conversions long, revenue double"
    return spark.createDataFrame(values, schema=schema)


def test_valid_campaign_metrics_pass(spark):
    df = rows(spark, [("2026-10-01", "google", "c1", 100, 20, 15.0, 3, 40.0)])
    assert assert_quality(df)["row_count"] == 1


def test_invalid_rows_are_counted_without_discarding(spark):
    df = rows(spark, [
        ("2026-10-01", "google", "c1", 10, 12, -1.0, 2, 4.0),
        ("2026-10-02", " ", "c2", 20, 2, 1.0, None, 5.0),
    ])
    report = quality_report(df).first().asDict()
    assert report["row_count"] == 2
    assert report["negative_metrics"] == 1
    assert report["clicks_exceed_impressions"] == 1
    assert report["invalid_keys"] == 1
    assert report["null_metrics"] == 1
    with pytest.raises(ValueError, match="data-quality gate failed"):
        assert_quality(df)


def test_missing_schema_fails_early(spark):
    df = spark.createDataFrame([(1,)], ["impressions"])
    with pytest.raises(ValueError, match="Missing required columns"):
        quality_report(df)
