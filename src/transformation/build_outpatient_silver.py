from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import quote_identifier, sql_literal
from src.transformation.outpatient_silver import (
    DEFAULT_CONTRACT_PATH,
    OutpatientSilverError,
    load_contract,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    service_volume_band_expression,
    source_measure_columns,
    suppression_status_expression,
)


def scalar_count(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any],
) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def parquet_columns(
    connection: duckdb.DuckDBPyConnection, bronze_glob: str
) -> list[str]:
    return [
        row[0]
        for row in connection.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [bronze_glob]
        ).fetchall()
    ]


def invalid_numeric_value_count(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    measures: list[str],
    contract: dict[str, Any],
) -> int:
    integers = set(contract["numeric_typing"]["integer_columns"])
    expressions = []
    for column in measures:
        source = quote_identifier(column)
        target_type = (
            contract["numeric_typing"]["integer_type"]
            if column in integers
            else contract["numeric_typing"]["decimal_type"]
        )
        expressions.append(
            "COUNT(*) FILTER ("
            f"WHERE {source} IS NOT NULL "
            f"AND TRIM(CAST({source} AS VARCHAR)) <> '' "
            f"AND TRY_CAST(TRIM(CAST({source} AS VARCHAR)) "
            f"AS {target_type}) IS NULL)"
        )
    counts = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [bronze_glob],
    ).fetchone()
    return int(sum(counts))


def silver_select_sql(
    source_columns: list[str], contract: dict[str, Any], bronze_glob: str
) -> tuple[str, list[str]]:
    required = set(contract["source_dimensions"])
    required.update(contract["retained_lineage"])
    required.update(contract["source_schema"]["required_columns"])
    missing = sorted(required - set(source_columns))
    if missing:
        raise OutpatientSilverError(
            "Missing required source columns: " + ", ".join(missing)
        )

    measures = source_measure_columns(source_columns, contract)
    governed = [
        *contract["numeric_typing"]["integer_columns"],
        *contract["numeric_typing"]["decimal_columns"],
    ]
    if len(measures) != len(governed) or set(measures) != set(governed):
        raise OutpatientSilverError(
            f"Measure schema mismatch; observed={measures}, governed={governed}"
        )

    dimensions = [
        normalized_dimension_expression(source, target, contract)
        for source, target in contract["source_dimensions"].items()
    ]
    missing_indicators = [
        missing_dimension_indicator_expression(source, target, contract)
        for source, target in contract["source_dimensions"].items()
        if contract["nullable_dimension_policy"]
        .get(target, {})
        .get("preserve_missing_indicator")
    ]
    inner = (
        "SELECT\n  "
        + ",\n  ".join(
            [
                *dimensions,
                *missing_indicators,
                "CAST(_reporting_year AS INTEGER) AS reporting_period",
                *[
                    normalized_measure_expression(column, contract)
                    for column in measures
                ],
                *contract["retained_lineage"],
            ]
        )
        + "\nFROM read_parquet("
        + sql_literal(bronze_glob)
        + ")"
    )
    derived = [
        "*",
        suppression_status_expression("provider_apc_summary", contract),
        suppression_status_expression("beneficiary_count", contract),
        suppression_status_expression("outlier_detail", contract),
        service_volume_band_expression(contract),
        "average_medicare_allowed_amount > average_submitted_charge "
        "AS allowed_amount_above_submitted_charge",
        "average_medicare_payment > average_submitted_charge "
        "AS medicare_payment_above_submitted_charge",
        "average_medicare_outlier_amount > average_medicare_payment "
        "AS outlier_amount_above_regular_payment",
    ]
    return "SELECT\n  " + ",\n  ".join(
        derived
    ) + "\nFROM (\n" + inner + "\n) typed", measures


def create_quality_report(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    silver_path: Path,
    source_columns: list[str],
    measures: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    silver = str(silver_path)

    def count(query: str, parameters: list[Any] | None = None) -> int:
        return scalar_count(connection, query, parameters or [silver])

    bronze_rows = count("SELECT COUNT(*) FROM read_parquet(?)", [bronze_glob])
    silver_rows = count("SELECT COUNT(*) FROM read_parquet(?)")
    duplicate_keys = count(
        """SELECT COUNT(*) FROM (
        SELECT hospital_ccn, comprehensive_apc_code, reporting_period
        FROM read_parquet(?) GROUP BY 1,2,3 HAVING COUNT(*) > 1)"""
    )
    null_keys = count(
        """SELECT COUNT(*) FROM read_parquet(?) WHERE hospital_ccn IS NULL
        OR comprehensive_apc_code IS NULL OR reporting_period IS NULL"""
    )

    def pattern_violations(column: str, pattern: str) -> int:
        return count(
            f"""SELECT COUNT(*) FROM read_parquet(?)
            WHERE {quote_identifier(column)} IS NULL
            OR NOT regexp_full_match({quote_identifier(column)}, ?)""",
            [silver, pattern.removeprefix("^").removesuffix("$")],
        )

    allowed = contract["allowed_values"]
    invalid_ccns = pattern_violations("hospital_ccn", allowed["ccn_pattern"])
    invalid_apcs = pattern_violations(
        "comprehensive_apc_code", allowed["comprehensive_apc_pattern"]
    )
    invalid_state_fips = pattern_violations(
        "hospital_state_fips", allowed["state_fips_pattern"]
    )
    invalid_zip5 = pattern_violations("hospital_zip5", allowed["zip5_pattern"])
    periods = [
        int(row[0])
        for row in connection.execute(
            "SELECT DISTINCT reporting_period FROM read_parquet(?) ORDER BY 1", [silver]
        ).fetchall()
    ]
    fractional_counts = count(
        """SELECT COUNT(*) FROM read_parquet(?) WHERE
        (beneficiary_count IS NOT NULL
         AND beneficiary_count <> TRUNC(beneficiary_count))
        OR (comprehensive_apc_services IS NOT NULL
            AND comprehensive_apc_services <> TRUNC(comprehensive_apc_services))
        OR (outlier_services IS NOT NULL
            AND outlier_services <> TRUNC(outlier_services))"""
    )
    negative_counts = count(
        """SELECT COUNT(*) FROM read_parquet(?) WHERE beneficiary_count < 0
        OR comprehensive_apc_services < 0 OR outlier_services < 0"""
    )
    negative_financial = count(
        """SELECT COUNT(*) FROM read_parquet(?) WHERE average_submitted_charge < 0
        OR average_medicare_allowed_amount < 0 OR average_medicare_payment < 0
        OR average_medicare_outlier_amount < 0"""
    )
    medicare_above_allowed = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE average_medicare_payment > average_medicare_allowed_amount"""
    )
    allowed_above_charge = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE allowed_amount_above_submitted_charge"""
    )
    payment_above_charge = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE medicare_payment_above_submitted_charge"""
    )
    outlier_above_payment = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE outlier_amount_above_regular_payment"""
    )
    summary_suppressed = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE provider_apc_summary_status = 'suppressed'"""
    )
    beneficiary_suppressed = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE beneficiary_count_status = 'suppressed'"""
    )
    outlier_suppressed = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE outlier_detail_status = 'suppressed'"""
    )
    missing_ruca_codes = count(
        "SELECT COUNT(*) FROM read_parquet(?) WHERE hospital_ruca_code_is_missing"
    )
    missing_ruca_descriptions = count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE hospital_ruca_description_is_missing"""
    )
    suppression = contract["suppression_semantics"]
    suppression_valid = (
        summary_suppressed
        == suppression["provider_apc_summary"]["observed_suppressed_rows"]
        and beneficiary_suppressed
        == summary_suppressed
        + suppression["beneficiary_count"]["observed_additional_suppressed_rows"]
        and outlier_suppressed
        == suppression["outlier_detail"]["observed_suppressed_rows"]
    )
    cms_columns = set(source_columns) - set(contract["retained_lineage"])
    schema_valid = (
        len(cms_columns) == contract["source_schema"]["expected_cms_column_count"]
        and len(set(source_columns) - cms_columns)
        == contract["source_schema"]["expected_lineage_column_count"]
        and set(contract["source_schema"]["required_columns"]).issubset(cms_columns)
    )
    rules = contract["quality_rules"]
    checks = {
        "preserve_source_row_count": bronze_rows == silver_rows,
        "require_unique_business_key": duplicate_keys == 0,
        "require_non_null_business_key": null_keys == 0,
        "require_valid_ccn": invalid_ccns == 0,
        "require_valid_comprehensive_apc_code": invalid_apcs == 0,
        "require_valid_state_fips": invalid_state_fips == 0,
        "require_valid_zip5": invalid_zip5 == 0,
        "retain_all_published_periods": periods == allowed["reporting_periods"],
        "prohibit_unavailable_period_interpolation": not contract[
            "available_period_policy"
        ]["interpolate_unavailable_periods"],
        "require_canonical_source_schema": schema_valid,
        "reject_unparseable_numeric_values": True,
        "require_integral_count_values": fractional_counts == 0,
        "require_nonnegative_count_values": negative_counts == 0,
        "require_nonnegative_financial_values": negative_financial == 0,
        "preserve_numeric_nulls": contract["numeric_typing"]["preserve_nulls"],
        "require_suppression_pattern_reconciliation": suppression_valid,
        "prohibit_suppressed_value_reconstruction": suppression[
            "prohibit_reconstruction"
        ],
        "require_medicare_payment_not_above_allowed_amount": medicare_above_allowed
        == 0,
        "report_allowed_above_submitted_charge": True,
        "report_payment_above_submitted_charge": True,
        "report_outlier_above_regular_payment": True,
        "require_nullable_dimension_policy": missing_ruca_codes
        == missing_ruca_descriptions,
        "require_period_specific_hospital_attributes": contract[
            "historical_attribute_handling"
        ]["preserve_reported_values_by_period"],
        "require_period_specific_apc_descriptions": contract[
            "apc_description_handling"
        ]["preserve_reported_description_by_period"],
        "require_peer_group_threshold_configuration": contract["benchmark_cohorts"][
            "minimum_peer_group_size"
        ]
        >= 11,
        "prohibit_real_hospital_anomaly_attribution": not contract[
            "privacy_and_reporting"
        ]["expose_real_hospital_anomaly_flags"],
    }
    if set(checks) != set(rules):
        raise OutpatientSilverError("Implemented checks do not match contract rules")
    return {
        "quality_report_version": 1,
        "model_name": contract["model"]["name"],
        "data_role": contract["model"]["data_role"],
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measures),
        "reporting_periods": periods,
        "suppression_counts": {
            "provider_apc_summary": summary_suppressed,
            "beneficiary_count": beneficiary_suppressed,
            "outlier_detail": outlier_suppressed,
        },
        "missing_ruca_code_count": missing_ruca_codes,
        "missing_ruca_description_count": missing_ruca_descriptions,
        "observed_relationship_counts": {
            "allowed_above_submitted_charge": allowed_above_charge,
            "payment_above_submitted_charge": payment_above_charge,
            "outlier_above_regular_payment": outlier_above_payment,
        },
        "violation_counts": {
            "duplicate_business_keys": duplicate_keys,
            "null_business_keys": null_keys,
            "invalid_ccns": invalid_ccns,
            "invalid_comprehensive_apc_codes": invalid_apcs,
            "invalid_state_fips": invalid_state_fips,
            "invalid_zip5": invalid_zip5,
            "fractional_count_values": fractional_counts,
            "negative_count_values": negative_counts,
            "negative_financial_values": negative_financial,
            "medicare_payment_above_allowed_amount": medicare_above_allowed,
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_outpatient_silver(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    paths = contract["paths"]
    bronze_glob = paths["bronze_glob"]
    silver_path = Path(paths["silver_output"])
    quality_path = Path(paths["quality_report"])
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect() as connection:
        source_columns = parquet_columns(connection, bronze_glob)
        silver_sql, measures = silver_select_sql(source_columns, contract, bronze_glob)
        invalid_values = invalid_numeric_value_count(
            connection, bronze_glob, measures, contract
        )
        if invalid_values:
            raise OutpatientSilverError(
                f"Unparseable numeric values found: {invalid_values}"
            )
        connection.execute(
            f"COPY ({silver_sql}) TO {sql_literal(str(silver_path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        report = create_quality_report(
            connection,
            bronze_glob,
            silver_path,
            source_columns,
            measures,
            contract,
        )
    quality_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not report["all_checks_passed"]:
        raise OutpatientSilverError(
            f"Outpatient Silver quality checks failed; see {quality_path}"
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the governed CMS outpatient Silver model."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def main() -> None:
    report = build_outpatient_silver(parse_args().contract)
    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(f"Suppression counts: {report['suppression_counts']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
