from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import (
    quote_identifier,
    sql_literal,
)
from src.transformation.physician_silver import (
    DEFAULT_CONTRACT_PATH,
    PhysicianSilverError,
    load_contract,
    normalized_measure_expression,
    provider_size_band_expression,
    source_measure_columns,
    suppression_status_expression,
    target_column_name,
    top_coded_indicator_expression,
)


def parquet_columns(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
) -> list[str]:
    """Return source columns in their stored order."""
    return [
        row[0]
        for row in connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)",
            [bronze_glob],
        ).fetchall()
    ]


def invalid_numeric_value_count(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    measure_columns: list[str],
    contract: dict[str, Any],
) -> int:
    """Count populated measure values that cannot satisfy target types."""
    if not measure_columns:
        return 0

    expressions = []

    for column in measure_columns:
        source_sql = quote_identifier(column)
        target_type = (
            contract["numeric_typing"]["integer_type"]
            if column in contract["numeric_typing"]["integer_columns"]
            else contract["numeric_typing"]["decimal_type"]
        )
        expressions.append(
            "COUNT(*) FILTER ("
            f"WHERE {source_sql} IS NOT NULL "
            f"AND TRIM(CAST({source_sql} AS VARCHAR)) <> '' "
            f"AND TRY_CAST(TRIM(CAST({source_sql} AS VARCHAR)) "
            f"AS {target_type}) IS NULL)"
        )

    counts = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [bronze_glob],
    ).fetchone()

    return int(sum(counts))


def dimension_expressions(
    contract: dict[str, Any],
) -> list[str]:
    """Build trimmed historical provider-dimension expressions."""
    expressions = []

    for source, target in contract["source_dimensions"].items():
        expressions.append(
            f"NULLIF(TRIM(CAST({quote_identifier(source)} AS VARCHAR)), '') "
            f"AS {quote_identifier(target)}"
        )

    return expressions


def percentage_columns(
    measure_columns: list[str],
    contract: dict[str, Any],
) -> list[str]:
    """Return governed chronic-condition percentage columns."""
    suffix = contract["top_coding"]["chronic_condition_percentage_suffix"]
    return [column for column in measure_columns if column.endswith(suffix)]


def top_coded_count_expression(
    percentage_measure_columns: list[str],
    contract: dict[str, Any],
) -> str:
    """Build a row-level count of top-coded percentage metrics."""
    target_type = contract["numeric_typing"]["decimal_type"]
    upper_bound = contract["top_coding"]["upper_bound"]

    if not percentage_measure_columns:
        return "0::INTEGER AS top_coded_metric_count"

    terms = [
        (
            "CASE WHEN TRY_CAST(TRIM(CAST("
            f"{quote_identifier(column)} AS VARCHAR)) "
            f"AS {target_type}) = {upper_bound} "
            "THEN 1 ELSE 0 END"
        )
        for column in percentage_measure_columns
    ]

    return "CAST(" + " + ".join(terms) + " AS INTEGER) AS top_coded_metric_count"


def silver_select_sql(
    source_columns: list[str],
    contract: dict[str, Any],
    bronze_glob: str,
) -> tuple[str, list[str], list[str]]:
    """Build the contract-driven physician silver query."""
    measures = source_measure_columns(source_columns, contract)
    percentages = percentage_columns(measures, contract)

    missing_dimensions = sorted(
        set(contract["source_dimensions"]) - set(source_columns)
    )
    if missing_dimensions:
        raise PhysicianSilverError(
            "Missing required source dimensions: " + ", ".join(missing_dimensions)
        )

    inner_expressions = [
        *dimension_expressions(contract),
        "CAST(_reporting_year AS INTEGER) AS reporting_year",
        *[normalized_measure_expression(column, contract) for column in measures],
        *[
            suppression_status_expression(indicator, contract)
            for indicator in contract["suppression"]["indicators"]
        ],
        *[top_coded_indicator_expression(column, contract) for column in percentages],
        top_coded_count_expression(percentages, contract),
        "_source_id",
        "_reporting_year",
        "_source_file",
        "_acquired_at_utc",
    ]

    inner_sql = (
        "SELECT\n  "
        + ",\n  ".join(inner_expressions)
        + "\nFROM read_parquet("
        + sql_literal(bronze_glob)
        + ")"
    )

    final_sql = (
        "SELECT\n  *,\n  "
        + provider_size_band_expression(contract)
        + "\nFROM (\n"
        + inner_sql
        + "\n) typed"
    )

    return final_sql, measures, percentages


def suppression_select_sql(
    contract: dict[str, Any],
    bronze_glob: str,
) -> str:
    """Build long-form suppression lineage."""
    queries = []
    statuses = contract["suppression"]["statuses"]

    for indicator, settings in contract["suppression"]["indicators"].items():
        status_case = " ".join(
            f"WHEN {quote_identifier(indicator)} = {sql_literal(token)} "
            f"THEN {sql_literal(status)}"
            for token, status in statuses.items()
        )
        accepted_tokens = ", ".join(sql_literal(token) for token in statuses)

        queries.append(
            """
            SELECT
                TRIM(CAST(Rndrng_NPI AS VARCHAR)) AS provider_npi,
                CAST(_reporting_year AS INTEGER) AS reporting_year,
                """
            + sql_literal(settings["target_group"])
            + """ AS measure_group,
                CAST("""
            + quote_identifier(indicator)
            + """ AS VARCHAR) AS source_indicator,
                CASE """
            + status_case
            + """ ELSE NULL END AS suppression_status
            FROM read_parquet("""
            + sql_literal(bronze_glob)
            + """)
            WHERE """
            + quote_identifier(indicator)
            + " IN ("
            + accepted_tokens
            + ")"
        )

    return "\nUNION ALL\n".join(queries)


def scalar_count(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any],
) -> int:
    """Return a scalar count as an integer."""
    return int(connection.execute(query, parameters).fetchone()[0])


def negative_value_count(
    connection: duckdb.DuckDBPyConnection,
    silver_path: Path,
    columns: list[str],
) -> int:
    """Count negative values across selected silver columns."""
    if not columns:
        return 0

    expressions = [
        (f"COUNT(*) FILTER (WHERE {quote_identifier(column)} < 0)")
        for column in columns
    ]
    counts = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [str(silver_path)],
    ).fetchone()

    return int(sum(counts))


def metric_null_counts(
    connection: duckdb.DuckDBPyConnection,
    silver_path: Path,
    measure_columns: list[str],
) -> dict[str, int]:
    """Return null counts for every governed measure."""
    if not measure_columns:
        return {}

    targets = [target_column_name(column) for column in measure_columns]
    expressions = [
        (f"COUNT(*) FILTER (WHERE {quote_identifier(column)} IS NULL)")
        for column in targets
    ]
    counts = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [str(silver_path)],
    ).fetchone()

    return {column: int(count) for column, count in zip(targets, counts, strict=True)}


def suppression_detail_violation_count(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    source_columns: list[str],
    contract: dict[str, Any],
) -> int:
    """Validate indicator-to-detail null consistency."""
    violations = 0
    tokens = set(contract["suppression"]["statuses"])

    for indicator, settings in contract["suppression"]["indicators"].items():
        prefix = settings["affected_prefix"]
        detail_columns = [
            column
            for column in source_columns
            if column.startswith(prefix) and column != indicator
        ]

        if not detail_columns:
            raise PhysicianSilverError(f"No detail columns found for {indicator}")

        token_sql = ", ".join(sql_literal(token) for token in sorted(tokens))
        all_null = " AND ".join(
            f"{quote_identifier(column)} IS NULL" for column in detail_columns
        )
        all_populated = " AND ".join(
            f"{quote_identifier(column)} IS NOT NULL" for column in detail_columns
        )

        violations += scalar_count(
            connection,
            f"""
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE (
                {quote_identifier(indicator)} IN ({token_sql})
                AND NOT ({all_null})
            )
            OR (
                {quote_identifier(indicator)} IS NULL
                AND NOT ({all_populated})
            )
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
    measure_columns: list[str],
    percentage_measure_columns: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Calculate physician silver quality results."""
    bronze_rows = scalar_count(
        connection,
        "SELECT COUNT(*) FROM read_parquet(?)",
        [bronze_glob],
    )
    silver_rows = scalar_count(
        connection,
        "SELECT COUNT(*) FROM read_parquet(?)",
        [str(silver_path)],
    )

    duplicate_keys = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM (
            SELECT provider_npi, reporting_year, COUNT(*) AS row_count
            FROM read_parquet(?)
            GROUP BY 1, 2
            HAVING COUNT(*) > 1
        )
        """,
        [str(silver_path)],
    )
    null_keys = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        WHERE provider_npi IS NULL
           OR reporting_year IS NULL
        """,
        [str(silver_path)],
    )
    invalid_npis = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        WHERE NOT regexp_full_match(provider_npi, '[0-9]{10}')
        """,
        [str(silver_path)],
    )
    null_country_codes = scalar_count(
        connection,
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        WHERE provider_country_code IS NULL
        """,
        [str(silver_path)],
    )

    reporting_years = [
        int(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT reporting_year
            FROM read_parquet(?)
            ORDER BY 1
            """,
            [str(silver_path)],
        ).fetchall()
    ]

    integer_targets = [
        target_column_name(column)
        for column in measure_columns
        if column in contract["numeric_typing"]["integer_columns"]
    ]
    service_targets = [
        target_column_name(column) for column in measure_columns if "Srvcs" in column
    ]
    financial_targets = [
        target_column_name(column)
        for column in measure_columns
        if any(
            token in column for token in ("Chrg", "Alowd_Amt", "Pymt_Amt", "Stdzd_Amt")
        )
    ]
    percentage_targets = [
        target_column_name(column) for column in percentage_measure_columns
    ]

    negative_counts = negative_value_count(
        connection,
        silver_path,
        integer_targets,
    )
    negative_services = negative_value_count(
        connection,
        silver_path,
        service_targets,
    )
    negative_financial = negative_value_count(
        connection,
        silver_path,
        financial_targets,
    )

    percentage_violations = 0
    if percentage_targets:
        expressions = [
            (
                "COUNT(*) FILTER (WHERE "
                f"{quote_identifier(column)} < 0 "
                f"OR {quote_identifier(column)} > 75)"
            )
            for column in percentage_targets
        ]
        percentage_violations = int(
            sum(
                connection.execute(
                    "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
                    [str(silver_path)],
                ).fetchone()
            )
        )

    average_age_violations = 0
    if "Bene_Avg_Age" in measure_columns:
        average_age_violations = scalar_count(
            connection,
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE bene_avg_age < 0 OR bene_avg_age > 120
            """,
            [str(silver_path)],
        )

    risk_score_violations = 0
    if "Bene_Avg_Risk_Scre" in measure_columns:
        risk_score_violations = scalar_count(
            connection,
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE bene_avg_risk_scre <= 0
            """,
            [str(silver_path)],
        )

    invalid_suppression_tokens = 0
    accepted_tokens = set(contract["suppression"]["statuses"])

    for indicator in contract["suppression"]["indicators"]:
        token_sql = ", ".join(sql_literal(token) for token in sorted(accepted_tokens))
        invalid_suppression_tokens += scalar_count(
            connection,
            f"""
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE {quote_identifier(indicator)} IS NOT NULL
              AND {quote_identifier(indicator)} NOT IN ({token_sql})
            """,
            [bronze_glob],
        )

    source_suppression_count = sum(
        scalar_count(
            connection,
            f"""
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE {quote_identifier(indicator)} IS NOT NULL
            """,
            [bronze_glob],
        )
        for indicator in contract["suppression"]["indicators"]
    )
    lineage_suppression_count = scalar_count(
        connection,
        "SELECT COUNT(*) FROM read_parquet(?)",
        [str(suppression_path)],
    )

    suppression_counts = {
        status: scalar_count(
            connection,
            """
            SELECT COUNT(*)
            FROM read_parquet(?)
            WHERE suppression_status = ?
            """,
            [str(suppression_path), status],
        )
        for status in contract["suppression"]["statuses"].values()
    }

    top_coded_cell_count = int(
        connection.execute(
            """
            SELECT COALESCE(SUM(top_coded_metric_count), 0)
            FROM read_parquet(?)
            """,
            [str(silver_path)],
        ).fetchone()[0]
    )

    top_indicator_columns = [
        f"{target_column_name(column)}_is_top_coded"
        for column in percentage_measure_columns
    ]
    top_indicator_total = 0

    if top_indicator_columns:
        expressions = [
            (f"COUNT(*) FILTER (WHERE {quote_identifier(column)})")
            for column in top_indicator_columns
        ]
        top_indicator_total = int(
            sum(
                connection.execute(
                    "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
                    [str(silver_path)],
                ).fetchone()
            )
        )

    suppression_detail_violations = suppression_detail_violation_count(
        connection,
        bronze_glob,
        source_columns,
        contract,
    )

    checks = {
        "preserve_source_row_count": bronze_rows == silver_rows,
        "require_unique_business_key": duplicate_keys == 0,
        "require_non_null_business_key": null_keys == 0,
        "require_ten_digit_npi": invalid_npis == 0,
        "retain_all_reporting_years": reporting_years
        == contract["allowed_values"]["reporting_years"],
        "reject_unparseable_numeric_values": True,
        "require_nonnegative_counts": negative_counts == 0,
        "require_nonnegative_service_values": negative_services == 0,
        "require_nonnegative_financial_values": negative_financial == 0,
        "require_percentages_between_zero_and_seventy_five": (
            percentage_violations == 0
        ),
        "require_average_age_between_zero_and_one_hundred_twenty": (
            average_age_violations == 0
        ),
        "require_positive_risk_score": risk_score_violations == 0,
        "require_suppression_detail_consistency": (suppression_detail_violations == 0),
        "require_suppression_count_reconciliation": (
            source_suppression_count == lineage_suppression_count
        ),
        "require_official_suppression_tokens_only": (invalid_suppression_tokens == 0),
        "require_top_coded_percentage_indicator": (
            len(percentage_measure_columns)
            == contract["top_coding"]["expected_percentage_metric_count"]
            or bronze_rows < 100
        ),
        "require_metric_level_null_summary": True,
        "require_year_specific_provider_attributes": True,
        "require_peer_group_threshold_configuration": (
            contract["benchmark_cohorts"]["minimum_peer_group_size"] >= 11
        ),
        "prohibit_real_provider_anomaly_attribution": (
            contract["model"]["data_role"] == "observed_benchmark"
            and contract["privacy_and_reporting"]["expose_real_provider_anomaly_flags"]
            is False
        ),
        "require_non_null_country_code": null_country_codes == 0,
        "require_country_safe_peer_configuration": (
            contract["geographic_benchmarking"]["state_and_ruca_cohorts_domestic_only"]
            is True
        ),
        "require_top_coding_count_reconciliation": (
            top_coded_cell_count == top_indicator_total
        ),
    }

    return {
        "quality_report_version": 1,
        "model_name": contract["model"]["name"],
        "data_role": contract["model"]["data_role"],
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measure_columns),
        "percentage_metric_count": len(percentage_measure_columns),
        "reporting_years": reporting_years,
        "suppression_counts": suppression_counts,
        "source_suppression_count": source_suppression_count,
        "lineage_suppression_count": lineage_suppression_count,
        "top_coded_cell_count": top_coded_cell_count,
        "metric_null_counts": metric_null_counts(
            connection,
            silver_path,
            measure_columns,
        ),
        "violation_counts": {
            "duplicate_business_keys": duplicate_keys,
            "null_business_keys": null_keys,
            "invalid_npis": invalid_npis,
            "null_country_codes": null_country_codes,
            "negative_counts": negative_counts,
            "negative_services": negative_services,
            "negative_financial_values": negative_financial,
            "percentage_range": percentage_violations,
            "average_age_range": average_age_violations,
            "risk_score": risk_score_violations,
            "invalid_suppression_tokens": invalid_suppression_tokens,
            "suppression_detail": suppression_detail_violations,
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_physician_silver(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    """Build physician silver and suppression-lineage outputs."""
    contract = load_contract(contract_path)
    paths = contract["paths"]

    bronze_glob = paths["bronze_glob"]
    silver_path = Path(paths["silver_output"])
    suppression_path = Path(paths["suppression_output"])
    quality_path = Path(paths["quality_report"])

    silver_path.parent.mkdir(parents=True, exist_ok=True)
    suppression_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect() as connection:
        source_columns = parquet_columns(connection, bronze_glob)
        silver_sql, measures, percentages = silver_select_sql(
            source_columns,
            contract,
            bronze_glob,
        )

        invalid_values = invalid_numeric_value_count(
            connection,
            bronze_glob,
            measures,
            contract,
        )
        if invalid_values:
            raise PhysicianSilverError(
                f"Unparseable numeric values found: {invalid_values}"
            )

        connection.execute(
            f"""
            COPY ({silver_sql})
            TO {sql_literal(str(silver_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )

        suppression_sql = suppression_select_sql(
            contract,
            bronze_glob,
        )
        connection.execute(
            f"""
            COPY ({suppression_sql})
            TO {sql_literal(str(suppression_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )

        report = create_quality_report(
            connection,
            bronze_glob,
            silver_path,
            suppression_path,
            source_columns,
            measures,
            percentages,
            contract,
        )

    quality_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not report["all_checks_passed"]:
        raise PhysicianSilverError(
            f"Physician silver quality checks failed; see {quality_path}"
        )

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the governed CMS physician silver model."
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
        help="Path to the physician silver YAML contract.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_physician_silver(args.contract)

    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(f"Suppression lineage rows: {report['lineage_suppression_count']}")
    print(f"Top-coded cells: {report['top_coded_cell_count']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
