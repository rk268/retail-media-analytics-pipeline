"""Bronze-to-Silver normalization for simulated Retail Media campaign data."""

import argparse
from pyspark.sql import SparkSession, functions as F, types as T


EXPECTED_COLUMNS = [
    "event_date",
    "platform",
    "campaign_id",
    "campaign_name",
    "impressions",
    "clicks",
    "spend",
    "conversions",
    "revenue",
]


def build_spark() -> SparkSession:
    return (
        SparkSession.builder
        .appName("retail-media-bronze-to-silver")
        .getOrCreate()
    )


def normalize(df):
    missing = sorted(set(EXPECTED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    clean = (
        df.select(*EXPECTED_COLUMNS)
        .withColumn("event_date", F.to_date("event_date"))
        .withColumn("platform", F.lower(F.trim("platform")))
        .withColumn("campaign_id", F.trim("campaign_id"))
        .withColumn("campaign_name", F.trim("campaign_name"))
        .withColumn("impressions", F.col("impressions").cast(T.LongType()))
        .withColumn("clicks", F.col("clicks").cast(T.LongType()))
        .withColumn("spend", F.col("spend").cast(T.DoubleType()))
        .withColumn("conversions", F.col("conversions").cast(T.LongType()))
        .withColumn("revenue", F.col("revenue").cast(T.DoubleType()))
        .dropDuplicates(["event_date", "platform", "campaign_id"])
    )

    invalid = (
        (F.col("event_date").isNull())
        | (F.col("impressions") < 0)
        | (F.col("clicks") < 0)
        | (F.col("spend") < 0)
        | (F.col("conversions") < 0)
        | (F.col("revenue") < 0)
        | (F.col("clicks") > F.col("impressions"))
    )

    return clean.filter(~invalid)


def main(input_path: str, output_path: str) -> None:
    spark = build_spark()
    raw = spark.read.option("header", True).csv(input_path)
    silver = normalize(raw)

    (
        silver.write
        .mode("overwrite")
        .partitionBy("event_date")
        .parquet(output_path)
    )

    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.input, args.output)
