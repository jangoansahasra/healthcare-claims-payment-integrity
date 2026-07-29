from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import quote_identifier, sql_literal
from src.transformation.part_d_silver import (
    DEFAULT_CONTRACT_PATH,
    PartDSilverError,
    load_contract,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    prescriber_size_band_expression,
    source_measure_columns,
    suppression_status_expression,
    target_column_name,
)


def parquet_columns(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [bronze_glob]
        ).fetchall()
    ]


def scalar_count(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any],
) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def invalid_numeric_value_count(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    measures: list[str],
    contract: dict[str, Any],
) -> int:
    expressions = []
    integers = set(contract["numeric_typing"]["integer_columns"])
    for column in measures:
        target_type = (
            contract["numeric_typing"]["integer_type"]
            if column in integers
            else contract["numeric_typing"]["decimal_type"]
        )
        source = quote_identifier(column)
        expressions.append(
            "COUNT(*) FILTER ("
            f"WHERE {source} IS NOT NULL "
            f"AND TRIM(CAST({source} AS VARCHAR)) <> '' "
            f"AND TRY_CAST(TRIM(CAST({source} AS VARCHAR)) "
            f"AS {target_type}) IS NULL)"
        )
    if not expressions:
        return 0
    values = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [bronze_glob],
    ).fetchone()
    return int(sum(values))


def silver_select_sql(
    source_columns: list[str],
    contract: dict[str, Any],
    bronze_glob: str,
) -> tuple[str, list[str]]:
    required = set(contract["source_dimensions"])
    required.update(contract["retained_lineage"])
    required.update(contract["suppression"]["indicators"])
    missing = sorted(required - set(source_columns))
    if missing:
        raise PartDSilverError("Missing required source columns: " + ", ".join(missing))

    measures = source_measure_columns(source_columns, contract)
    governed = set(contract["numeric_typing"]["integer_columns"])
    governed.update(
        column
        for columns in contract["numeric_typing"]["decimal_measure_classes"].values()
        for column in columns
    )
    if set(measures) != governed:
        unknown = sorted(set(measures) - governed)
        absent = sorted(governed - set(measures))
        raise PartDSilverError(
            f"Measure schema mismatch; unknown={unknown}, missing={absent}"
        )

    expressions = [
        *[
            normalized_dimension_expression(source, target, contract)
            for source, target in contract["source_dimensions"].items()
        ],
        *[
            missing_dimension_indicator_expression(source, target, contract)
            for source, target in contract["source_dimensions"].items()
            if contract["nullable_dimension_policy"]
            .get(target, {})
            .get("preserve_missing_indicator")
        ],
        "CAST(_reporting_year AS INTEGER) AS reporting_year",
        *[normalized_measure_expression(column, contract) for column in measures],
        *[
            suppression_status_expression(indicator, contract)
            for indicator in contract["suppression"]["indicators"]
        ],
        *contract["retained_lineage"],
    ]
    inner = (
        "SELECT\n  "
        + ",\n  ".join(expressions)
        + "\nFROM read_parquet("
        + sql_literal(bronze_glob)
        + ")"
    )
    return (
        "SELECT\n  *,\n  "
        + prescriber_size_band_expression(contract)
        + "\nFROM (\n"
        + inner
        + "\n) typed",
        measures,
    )


def suppression_select_sql(
    contract: dict[str, Any],
    bronze_glob: str,
) -> str:
    queries = []
    statuses = contract["suppression"]["statuses"]
    for indicator, settings in contract["suppression"]["indicators"].items():
        tokens = settings["allowed_tokens"]
        source = f"TRIM(CAST({quote_identifier(indicator)} AS VARCHAR))"
        cases = " ".join(
            f"WHEN {source} = {sql_literal(token)} THEN {sql_literal(statuses[token])}"
            for token in tokens
        )
        token_sql = ", ".join(sql_literal(token) for token in tokens)
        queries.append(
            "SELECT "
            "TRIM(CAST(Prscrbr_NPI AS VARCHAR)) AS prescriber_npi, "
            "CAST(_reporting_year AS INTEGER) AS reporting_year, "
            f"{sql_literal(settings['target_group'])} AS measure_group, "
            f"CAST({quote_identifier(indicator)} AS VARCHAR) AS source_indicator, "
            f"CASE {cases} ELSE NULL END AS suppression_status "
            f"FROM read_parquet({sql_literal(bronze_glob)}) "
            f"WHERE {source} IN ({token_sql})"
        )
    return "\nUNION ALL\n".join(queries)


def negative_value_count(
    connection: duckdb.DuckDBPyConnection,
    silver_path: Path,
    columns: list[str],
) -> int:
    if not columns:
        return 0
    counts = connection.execute(
        "SELECT "
        + ", ".join(
            f"COUNT(*) FILTER (WHERE {quote_identifier(column)} < 0)"
            for column in columns
        )
        + " FROM read_parquet(?)",
        [str(silver_path)],
    ).fetchone()
    return int(sum(counts))


def metric_null_counts(
    connection: duckdb.DuckDBPyConnection,
    silver_path: Path,
    measures: list[str],
) -> dict[str, int]:
    targets = [target_column_name(column) for column in measures]
    counts = connection.execute(
        "SELECT "
        + ", ".join(
            f"COUNT(*) FILTER (WHERE {quote_identifier(column)} IS NULL)"
            for column in targets
        )
        + " FROM read_parquet(?)",
        [str(silver_path)],
    ).fetchone()
    return dict(zip(targets, map(int, counts), strict=True))


def suppression_detail_violation_count(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    contract: dict[str, Any],
) -> int:
    violations = 0
    for indicator, settings in contract["suppression"]["indicators"].items():
        source = f"TRIM(CAST({quote_identifier(indicator)} AS VARCHAR))"
        tokens = ", ".join(sql_literal(token) for token in settings["allowed_tokens"])
        details = settings["affected_measures"]
        all_null = " AND ".join(
            f"{quote_identifier(column)} IS NULL" for column in details
        )
        all_present = " AND ".join(
            f"{quote_identifier(column)} IS NOT NULL" for column in details
        )
        violations += scalar_count(
            connection,
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE ({source} IN ({tokens}) AND NOT ({all_null}))
               OR ({source} IS NULL AND NOT ({all_present}))
            """,
            [bronze_glob],
        )
    return violations


def create_quality_report(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    silver_path: Path,
    suppression_path: Path,
    source_columns: list[str],
    measures: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    bronze_rows = scalar_count(
        connection, "SELECT COUNT(*) FROM read_parquet(?)", [bronze_glob]
    )
    silver_rows = scalar_count(
        connection, "SELECT COUNT(*) FROM read_parquet(?)", [str(silver_path)]
    )
    duplicate_keys = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM (
          SELECT prescriber_npi, reporting_year
          FROM read_parquet(?) GROUP BY 1, 2 HAVING COUNT(*) > 1
        )
        """,
        [str(silver_path)],
    )
    null_keys = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE prescriber_npi IS NULL OR reporting_year IS NULL
        """,
        [str(silver_path)],
    )
    invalid_npis = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE NOT regexp_full_match(prescriber_npi, '[0-9]{10}')
        """,
        [str(silver_path)],
    )
    years = [
        int(row[0])
        for row in connection.execute(
            "SELECT DISTINCT reporting_year FROM read_parquet(?) ORDER BY 1",
            [str(silver_path)],
        ).fetchall()
    ]

    integer_sources = contract["numeric_typing"]["integer_columns"]
    integer_targets = [target_column_name(column) for column in integer_sources]
    fractional = sum(
        scalar_count(
            connection,
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE {quote_identifier(column)} IS NOT NULL
              AND {quote_identifier(column)} <> TRUNC({quote_identifier(column)})
            """,
            [str(silver_path)],
        )
        for column in integer_targets
    )
    count_targets = [
        target_column_name(column)
        for column in integer_sources
        if "Cnt" in column or "Clms" in column or "Benes" in column
    ]
    fill_targets = [
        target_column_name(column) for column in measures if "30day_Fills" in column
    ]
    cost_targets = [
        target_column_name(column) for column in measures if "Cst" in column
    ]
    supply_targets = [
        target_column_name(column) for column in measures if "Suply" in column
    ]
    rate_targets = [
        target_column_name(column) for column in measures if column.endswith("_Rate")
    ]

    def range_count(columns: list[str], predicate: str) -> int:
        return sum(
            scalar_count(
                connection,
                "SELECT COUNT(*) FROM read_parquet(?) WHERE "
                + predicate.format(column=quote_identifier(column)),
                [str(silver_path)],
            )
            for column in columns
        )

    invalid_tokens = 0
    source_suppression_count = 0
    for indicator, settings in contract["suppression"]["indicators"].items():
        source = f"TRIM(CAST({quote_identifier(indicator)} AS VARCHAR))"
        tokens = ", ".join(sql_literal(token) for token in settings["allowed_tokens"])
        invalid_tokens += scalar_count(
            connection,
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE {source} IS NOT NULL
              AND {source} NOT IN ({tokens})
            """,
            [bronze_glob],
        )
        source_suppression_count += scalar_count(
            connection,
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE {source} IN ({tokens})
            """,
            [bronze_glob],
        )

    lineage_count = scalar_count(
        connection, "SELECT COUNT(*) FROM read_parquet(?)", [str(suppression_path)]
    )
    suppression_counts = {
        status: scalar_count(
            connection,
            "SELECT COUNT(*) FROM read_parquet(?) WHERE suppression_status = ?",
            [str(suppression_path), status],
        )
        for status in contract["suppression"]["statuses"].values()
    }
    detail_violations = suppression_detail_violation_count(
        connection, bronze_glob, contract
    )

    violation_counts = {
        "duplicate_business_keys": duplicate_keys,
        "null_business_keys": null_keys,
        "invalid_npis": invalid_npis,
        "fractional_integer_values": fractional,
        "negative_counts": negative_value_count(connection, silver_path, count_targets),
        "negative_standardized_fills": negative_value_count(
            connection, silver_path, fill_targets
        ),
        "negative_drug_costs": negative_value_count(
            connection, silver_path, cost_targets
        ),
        "negative_days_supply": negative_value_count(
            connection, silver_path, supply_targets
        ),
        "rate_range": range_count(rate_targets, "{column} < 0 OR {column} > 100"),
        "average_age_range": range_count(
            ["bene_avg_age"], "{column} < 0 OR {column} > 120"
        ),
        "risk_score": range_count(["bene_avg_risk_scre"], "{column} <= 0"),
        "invalid_suppression_tokens": invalid_tokens,
        "suppression_detail": detail_violations,
    }
    cms_source_columns = set(source_columns) - set(contract["retained_lineage"])
    source_schema_valid = (
        len(cms_source_columns)
        == contract["source_schema"]["expected_source_column_count"]
    ) and set(contract["source_schema"]["required_canonical_columns"]).issubset(
        cms_source_columns
    )
    nullable_policy_valid = all(
        (
            settings.get("preserve_missing_indicator")
            and "silver_value_when_missing" in settings
        )
        for settings in contract["nullable_dimension_policy"].values()
        if "observed_null_or_blank_rows" in settings
    )
    checks = {
        "preserve_source_row_count": bronze_rows == silver_rows,
        "require_unique_business_key": duplicate_keys == 0,
        "require_non_null_business_key": null_keys == 0,
        "require_ten_digit_npi": invalid_npis == 0,
        "retain_all_reporting_years": years
        == contract["allowed_values"]["reporting_years"],
        "require_canonical_source_schema": source_schema_valid,
        "reject_unparseable_numeric_values": True,
        "require_integer_columns_without_fractional_values": fractional == 0,
        "require_nonnegative_counts": violation_counts["negative_counts"] == 0,
        "require_nonnegative_standardized_fills": (
            violation_counts["negative_standardized_fills"] == 0
        ),
        "require_nonnegative_drug_costs": (
            violation_counts["negative_drug_costs"] == 0
        ),
        "require_nonnegative_days_supply": (
            violation_counts["negative_days_supply"] == 0
        ),
        "require_rates_between_zero_and_one_hundred": (
            violation_counts["rate_range"] == 0
        ),
        "require_average_age_between_zero_and_one_hundred_twenty": (
            violation_counts["average_age_range"] == 0
        ),
        "require_positive_or_null_risk_score": (violation_counts["risk_score"] == 0),
        "require_official_suppression_tokens_only": invalid_tokens == 0,
        "require_suppression_detail_consistency": detail_violations == 0,
        "require_suppression_count_reconciliation": (
            source_suppression_count == lineage_count
        ),
        "require_metric_level_null_summary": True,
        "require_nullable_dimension_policy": nullable_policy_valid,
        "require_year_specific_prescriber_attributes": contract[
            "historical_attribute_handling"
        ]["preserve_reported_values_by_year"],
        "require_peer_group_threshold_configuration": contract["benchmark_cohorts"][
            "minimum_peer_group_size"
        ]
        >= 11,
        "require_country_safe_peer_configuration": contract["geographic_benchmarking"][
            "prohibit_cross_country_peer_comparisons"
        ],
        "prohibit_real_prescriber_anomaly_attribution": not contract[
            "privacy_and_reporting"
        ]["expose_real_prescriber_anomaly_flags"],
    }
    return {
        "quality_report_version": 1,
        "model_name": contract["model"]["name"],
        "data_role": contract["model"]["data_role"],
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measures),
        "reporting_years": years,
        "suppression_counts": suppression_counts,
        "source_suppression_count": source_suppression_count,
        "lineage_suppression_count": lineage_count,
        "metric_null_counts": metric_null_counts(connection, silver_path, measures),
        "violation_counts": violation_counts,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_part_d_silver(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    paths = contract["paths"]
    bronze_glob = paths["bronze_glob"]
    silver_path = Path(paths["silver_output"])
    suppression_path = Path(paths["suppression_output"])
    quality_path = Path(paths["quality_report"])
    for path in (silver_path, suppression_path, quality_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect() as connection:
        source_columns = parquet_columns(connection, bronze_glob)
        silver_sql, measures = silver_select_sql(source_columns, contract, bronze_glob)
        invalid = invalid_numeric_value_count(
            connection, bronze_glob, measures, contract
        )
        if invalid:
            raise PartDSilverError(f"Unparseable numeric values found: {invalid}")

        connection.execute(
            f"COPY ({silver_sql}) TO {sql_literal(str(silver_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        connection.execute(
            f"COPY ({suppression_select_sql(contract, bronze_glob)}) "
            f"TO {sql_literal(str(suppression_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        report = create_quality_report(
            connection,
            bronze_glob,
            silver_path,
            suppression_path,
            source_columns,
            measures,
            contract,
        )

    quality_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not report["all_checks_passed"]:
        raise PartDSilverError(
            f"Part D silver quality checks failed; see {quality_path}"
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the governed CMS Part D prescriber silver model."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def main() -> None:
    report = build_part_d_silver(parse_args().contract)
    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(f"Suppression lineage rows: {report['lineage_suppression_count']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
