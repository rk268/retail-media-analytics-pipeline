"""Reusable Spark data-quality gates for retail media campaign metrics.

Run on normalized silver records before aggregating to gold. No proprietary data.
"""
from pyspark.sql import functions as F

REQUIRED = ("event_date", "platform", "campaign_id", "impressions", "clicks", "spend", "conversions", "revenue")
METRICS = ("impressions", "clicks", "spend", "conversions", "revenue")
KEYS = ("event_date", "platform", "campaign_id")


def quality_report(df):
    """Return a one-row DataFrame of violation counts; does not silently drop rows."""
    missing = sorted(set(REQUIRED) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    invalid_key = F.lit(False)
    for key in KEYS:
        invalid_key = invalid_key | F.col(key).isNull()
    for key in ("platform", "campaign_id"):
        invalid_key = invalid_key | (F.length(F.trim(F.col(key))) == 0)

    negative = F.lit(False)
    null_metric = F.lit(False)
    for metric in METRICS:
        negative = negative | (F.col(metric) < 0)
        null_metric = null_metric | F.col(metric).isNull()

    return df.agg(
        F.count(F.lit(1)).alias("row_count"),
        F.sum(F.when(invalid_key, 1).otherwise(0)).alias("invalid_keys"),
        F.sum(F.when(null_metric, 1).otherwise(0)).alias("null_metrics"),
        F.sum(F.when(negative, 1).otherwise(0)).alias("negative_metrics"),
        F.sum(F.when(F.col("clicks") > F.col("impressions"), 1).otherwise(0)).alias("clicks_exceed_impressions"),
    )


def assert_quality(df):
    """Fail the pipeline when any row violates the declared business rules."""
    counts = quality_report(df).first().asDict()
    failures = {k: v for k, v in counts.items() if k != "row_count" and v}
    if failures:
        raise ValueError(f"Retail media data-quality gate failed: {failures}")
    return counts
