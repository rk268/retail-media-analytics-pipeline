"""Date-scoped, idempotent daily Gold publication for simulated retail media.

Unlike the all-time Gold aggregate, this module preserves untouched date
partitions when rerunning one day's Silver input. Parquet writes are not ACID.
"""
from __future__ import annotations

import argparse
from datetime import date
import re

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DateType

from src.data_quality import KEYS, assert_quality
from src.silver_to_gold import safe_divide


def parse_day(value: str) -> date:
    """Require an unambiguous ISO calendar date, not a lenient Spark cast."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("--date must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("--date is not a valid calendar day") from exc


def build_daily_gold(silver, day: str):
    """Validate Silver, then aggregate exactly one event-date partition."""
    target = parse_day(day)
    if "campaign_name" not in silver.columns:
        raise ValueError("Missing required column: campaign_name")
    if not isinstance(silver.schema["event_date"].dataType, DateType):
        raise ValueError("Silver event_date must have Spark DateType")
    assert_quality(silver)  # fail closed before filtering, including other dates

    selected = silver.where(F.col("event_date") == F.lit(target))
    if selected.limit(1).count() == 0:
        raise ValueError(f"No Silver records for {day}; refusing empty overwrite")

    invalid = (
        F.col("campaign_name").isNull()
        | (F.length(F.trim(F.col("campaign_name"))) == 0)
        | F.isnan("spend") | F.isnan("revenue")
        | (F.abs(F.col("spend")) == float("inf"))
        | (F.abs(F.col("revenue")) == float("inf"))
    )
    if selected.where(invalid).limit(1).count():
        raise ValueError("Selected partition has invalid campaign names or nonfinite money")
    if (selected.groupBy(*KEYS).count()
            .where(F.col("count") > 1).limit(1).count()):
        raise ValueError("Duplicate (event_date, platform, campaign_id) in Silver")

    totals = (
        selected.groupBy("event_date", "platform", "campaign_id", "campaign_name")
        .agg(
            F.sum("impressions").alias("impressions"),
            F.sum("clicks").alias("clicks"),
            F.sum("spend").alias("spend"),
            F.sum("conversions").alias("conversions"),
            F.sum("revenue").alias("revenue"),
        )
    )
    return (
        totals.withColumn("ctr", safe_divide(F.col("clicks"), F.col("impressions")))
        .withColumn("cpc", safe_divide(F.col("spend"), F.col("clicks")))
        .withColumn("cpm", safe_divide(F.col("spend") * 1000.0, F.col("impressions")))
        .withColumn("conversion_rate", safe_divide(F.col("conversions"), F.col("clicks")))
        .withColumn("cpa", safe_divide(F.col("spend"), F.col("conversions")))
        .withColumn("roas", safe_divide(F.col("revenue"), F.col("spend")))
    )


def write_daily_partition(gold, output_path: str) -> None:
    """Dynamically overwrite one populated date partition; preserve others."""
    dates = gold.select("event_date").distinct().limit(2).collect()
    if len(dates) != 1 or dates[0][0] is None:
        raise ValueError("Gold output must contain exactly one nonnull event_date")
    (
        gold.write.option("partitionOverwriteMode", "dynamic")
        .mode("overwrite")
        .partitionBy("event_date")
        .parquet(output_path)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Silver Parquet dataset")
    parser.add_argument("--output", required=True, help="Partitioned daily Gold Parquet dataset")
    parser.add_argument("--date", required=True, help="Event date to refresh, YYYY-MM-DD")
    args = parser.parse_args()
    parse_day(args.date)  # fail before starting Spark
    spark = SparkSession.builder.appName("retail-media-incremental-gold").getOrCreate()
    try:
        silver = spark.read.parquet(args.input)
        gold = build_daily_gold(silver, args.date)
        write_daily_partition(gold, args.output)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
