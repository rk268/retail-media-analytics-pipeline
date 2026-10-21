"""Test Gold KPI aggregation and fail-closed Silver data validation."""
import pytest
from pyspark.sql import SparkSession
from src.silver_to_gold import build_gold


@pytest.fixture(scope="module")
def spark():
    session = SparkSession.builder.master("local[1]").appName("gold-quality-tests").getOrCreate()
    yield session
    session.stop()


SCHEMA = (
    "event_date string, platform string, campaign_id string, campaign_name string, "
    "impressions long, clicks long, spend double, conversions long, revenue double"
)


def test_gold_aggregates_weighted_kpis(spark):
    rows = [
        ("2026-10-01", "google", "c1", "Test Campaign", 100, 10, 20.0, 2, 100.0),
        ("2026-10-02", "google", "c1", "Test Campaign", 300, 30, 60.0, 6, 180.0),
    ]
    gold = build_gold(spark.createDataFrame(rows, SCHEMA)).first().asDict()
    assert gold["impressions"] == 400
    assert gold["clicks"] == 40
    assert gold["spend"] == pytest.approx(80.0)
    assert gold["ctr"] == pytest.approx(0.1)
    assert gold["cpc"] == pytest.approx(2.0)
    assert gold["cpm"] == pytest.approx(200.0)
    assert gold["cpa"] == pytest.approx(10.0)
    assert gold["roas"] == pytest.approx(3.5)


def test_gold_rejects_silver_negative_spend(spark):
    invalid = [("2026-10-01", "google", "c2", "Bad Campaign", 100, 5, -10.0, 1, 20.0)]
    with pytest.raises(ValueError, match="data-quality gate failed"):
        build_gold(spark.createDataFrame(invalid, SCHEMA))


def test_gold_rejects_missing_campaign_keys(spark):
    invalid = [("2026-10-01", " ", "c2", "Bad Campaign", 100, 5, 10.0, 1, 20.0)]
    with pytest.raises(ValueError, match="data-quality gate failed"):
        build_gold(spark.createDataFrame(invalid, SCHEMA))


def test_gold_zero_denominator_is_finite(spark):
    rows = [("2026-10-01", "meta", "c3", "Empty Campaign", 0, 0, 0.0, 0, 0.0)]
    gold = build_gold(spark.createDataFrame(rows, SCHEMA)).first().asDict()
    for key in ("ctr", "cpc", "cpm", "conversion_rate", "cpa", "roas"):
        assert gold[key] == pytest.approx(0.0)
