"""Silver-to-Gold aggregation for cross-channel Retail Media KPIs."""

import argparse
from pyspark.sql import SparkSession, functions as F


def safe_divide(numerator, denominator):
    return F.when(denominator > 0, numerator / denominator).otherwise(F.lit(0.0))


def build_gold(df):
    aggregated = (
        df.groupBy("platform", "campaign_id", "campaign_name")
        .agg(
            F.sum("impressions").alias("impressions"),
            F.sum("clicks").alias("clicks"),
            F.sum("spend").alias("spend"),
            F.sum("conversions").alias("conversions"),
            F.sum("revenue").alias("revenue"),
            F.min("event_date").alias("start_date"),
            F.max("event_date").alias("end_date"),
        )
    )

    return (
        aggregated
        .withColumn("ctr", safe_divide(F.col("clicks"), F.col("impressions")))
        .withColumn("cpc", safe_divide(F.col("spend"), F.col("clicks")))
        .withColumn("cpm", safe_divide(F.col("spend") * F.lit(1000.0), F.col("impressions")))
        .withColumn("conversion_rate", safe_divide(F.col("conversions"), F.col("clicks")))
        .withColumn("cpa", safe_divide(F.col("spend"), F.col("conversions")))
        .withColumn("roas", safe_divide(F.col("revenue"), F.col("spend")))
    )


def main(input_path: str, output_path: str) -> None:
    spark = SparkSession.builder.appName("retail-media-silver-to-gold").getOrCreate()
    silver = spark.read.parquet(input_path)
    gold = build_gold(silver)

    gold.write.mode("overwrite").parquet(output_path)
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.input, args.output)
