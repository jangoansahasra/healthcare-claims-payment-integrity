# ruff: noqa: F821
# Fabric notebook source for nb_hcpi_load_validate.
# Attach this notebook to the schema-enabled lh_hcpi_curated Lakehouse.

import json
from decimal import Decimal

from pyspark.sql import functions as F

MANIFEST_PATH = "/lakehouse/default/Files/manifest/table_manifest.json"
LANDING_ROOT = "Files"
COUNT_TOLERANCE = 0
FINANCIAL_TOLERANCE = Decimal("0.01")

with open(MANIFEST_PATH, encoding="utf-8") as stream:
    manifest = json.load(stream)

results = []
for item in manifest["tables"]:
    schema_name = item["domain"]
    table_name = item["table_name"]
    qualified_name = f"{schema_name}.{table_name}"
    source_path = f"{LANDING_ROOT}/{item['landing_path']}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    frame = spark.read.parquet(source_path)
    frame.write.format("delta").mode("overwrite").option(
        "overwriteSchema", "true"
    ).saveAsTable(qualified_name)
    loaded = spark.table(qualified_name)
    key_columns = item["primary_key"]
    actual_rows = loaded.count()
    actual_keys = loaded.select(*key_columns).distinct().count()
    results.append(
        {
            "table_name": qualified_name,
            "check_type": "row_and_primary_key_count",
            "expected_value": str(item["row_count"]),
            "actual_value": str(actual_rows),
            "passed": actual_rows == item["row_count"]
            and actual_keys == item["distinct_primary_key_count"],
        }
    )
    for measure, expected_text in item["governed_measure_totals"].items():
        actual = loaded.agg(F.sum(F.col(measure)).alias("value")).first()["value"]
        actual_decimal = Decimal(str(actual or 0))
        expected = Decimal(expected_text)
        results.append(
            {
                "table_name": qualified_name,
                "check_type": f"sum_{measure}",
                "expected_value": str(expected),
                "actual_value": str(actual_decimal),
                "passed": abs(actual_decimal - expected) <= FINANCIAL_TOLERANCE,
            }
        )

result_frame = spark.createDataFrame(results)
result_frame.write.format("delta").mode("overwrite").saveAsTable(
    "trusted.fabric_reconciliation_result"
)

failed = result_frame.filter(~F.col("passed")).count()
if failed:
    raise RuntimeError(f"Fabric reconciliation failed for {failed} checks")

display(result_frame.orderBy("table_name", "check_type"))
