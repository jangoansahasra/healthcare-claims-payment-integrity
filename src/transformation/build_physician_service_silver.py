from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import quote_identifier, sql_literal
from src.transformation.physician_service_silver import (
    DEFAULT_CONTRACT_PATH,
    PhysicianServiceSilverError,
    beneficiary_volume_band_expression,
    load_contract,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    source_measure_columns,
)


def count(
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


def invalid_numeric_count(
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
            f"AND TRY_CAST(TRIM(CAST({source} AS VARCHAR)) "
            f"AS {target_type}) IS NULL)"
        )
    values = connection.execute(
        "SELECT " + ", ".join(expressions) + " FROM read_parquet(?)",
        [bronze_glob],
    ).fetchone()
    return int(sum(values))


def silver_sql(
    source_columns: list[str], contract: dict[str, Any], bronze_glob: str
) -> tuple[str, list[str]]:
    required = set(contract["source_dimensions"])
    required.update(contract["retained_lineage"])
    required.update(contract["source_schema"]["required_columns"])
    missing = sorted(required - set(source_columns))
    if missing:
        raise PhysicianServiceSilverError(
            "Missing required columns: " + ", ".join(missing)
        )
    measures = source_measure_columns(source_columns, contract)
    governed = {
        *contract["numeric_typing"]["integer_columns"],
        *contract["numeric_typing"]["decimal_columns"],
    }
    if set(measures) != governed:
        raise PhysicianServiceSilverError(f"Measure schema mismatch: {measures}")
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
                "CAST(_reporting_year AS INTEGER) AS reporting_year",
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
        beneficiary_volume_band_expression(contract),
        "CASE WHEN provider_country_code = 'US' THEN 'United States' "
        "ELSE 'Foreign' END AS provider_geography_scope",
        "CASE WHEN provider_country_code = 'US' THEN provider_state_fips "
        "ELSE 'Not applicable' END AS peer_state_fips",
        "CASE WHEN provider_country_code = 'US' THEN provider_ruca_code "
        "ELSE 'Not applicable' END AS peer_ruca_code",
        "average_medicare_allowed_amount > average_submitted_charge "
        "AS allowed_amount_above_submitted_charge",
        "average_medicare_payment > average_submitted_charge "
        "AS medicare_payment_above_submitted_charge",
        "average_standardized_medicare_payment > average_medicare_allowed_amount "
        "AS standardized_payment_above_allowed_amount",
    ]
    return (
        "SELECT\n  " + ",\n  ".join(derived) + "\nFROM (\n" + inner + "\n) typed",
        measures,
    )


def quality_report(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    silver_path: Path,
    source_columns: list[str],
    measures: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    silver = str(silver_path)

    def silver_count(query: str, extra: list[Any] | None = None) -> int:
        return count(connection, query, [silver, *(extra or [])])

    bronze_rows = count(
        connection, "SELECT COUNT(*) FROM read_parquet(?)", [bronze_glob]
    )
    silver_rows = silver_count("SELECT COUNT(*) FROM read_parquet(?)")
    duplicate_keys = silver_count(
        """SELECT COUNT(*) FROM (
        SELECT rendering_npi, hcpcs_code, place_of_service_category,
               reporting_year
        FROM read_parquet(?) GROUP BY 1,2,3,4 HAVING COUNT(*) > 1)"""
    )
    null_keys = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE rendering_npi IS NULL OR hcpcs_code IS NULL
        OR place_of_service_category IS NULL OR reporting_year IS NULL"""
    )
    invalid_npis = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE NOT regexp_full_match(rendering_npi, '[0-9]{10}')"""
    )
    invalid_hcpcs = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE NOT regexp_full_match(hcpcs_code, '[0-9A-Za-z]{5}')"""
    )
    invalid_domains = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE provider_entity_code NOT IN ('I','O')
        OR place_of_service_category NOT IN ('F','O')
        OR hcpcs_drug_indicator NOT IN ('N','Y')
        OR medicare_participation_indicator NOT IN ('N','Y')"""
    )
    years = [
        int(row[0])
        for row in connection.execute(
            "SELECT DISTINCT reporting_year FROM read_parquet(?) ORDER BY 1", [silver]
        ).fetchall()
    ]
    fractional_benes = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE total_beneficiaries <> TRUNC(total_beneficiaries)"""
    )
    fractional_days = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE total_beneficiary_day_services
        <> TRUNC(total_beneficiary_day_services)"""
    )
    fractional_services = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE total_services <> TRUNC(total_services)"""
    )
    below_minimum = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE total_beneficiaries < ?""",
        [contract["publication_threshold"]["minimum_published_value"]],
    )
    negative_measures = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?) WHERE total_beneficiaries < 0
        OR total_services < 0 OR total_beneficiary_day_services < 0
        OR average_submitted_charge < 0
        OR average_medicare_allowed_amount < 0
        OR average_medicare_payment < 0
        OR average_standardized_medicare_payment < 0"""
    )
    payment_above_allowed = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE average_medicare_payment > average_medicare_allowed_amount"""
    )
    allowed_above_charge = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE allowed_amount_above_submitted_charge"""
    )
    payment_above_charge = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE medicare_payment_above_submitted_charge"""
    )
    standardized_above_allowed = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE standardized_payment_above_allowed_amount"""
    )
    missing_state_fips = silver_count(
        "SELECT COUNT(*) FROM read_parquet(?) WHERE provider_state_fips_is_missing"
    )
    missing_ruca = silver_count(
        "SELECT COUNT(*) FROM read_parquet(?) WHERE provider_ruca_code_is_missing"
    )
    foreign_peer_violations = silver_count(
        """SELECT COUNT(*) FROM read_parquet(?)
        WHERE provider_country_code <> 'US'
        AND (peer_state_fips <> 'Not applicable'
             OR peer_ruca_code <> 'Not applicable')"""
    )
    cms_columns = set(source_columns) - set(contract["retained_lineage"])
    schema_valid = (
        len(cms_columns) == contract["source_schema"]["expected_cms_column_count"]
        and len(set(source_columns) - cms_columns)
        == contract["source_schema"]["expected_lineage_column_count"]
    )
    checks = {
        "preserve_source_row_count": bronze_rows == silver_rows,
        "require_unique_business_key": duplicate_keys == 0,
        "require_non_null_business_key": null_keys == 0,
        "require_valid_npi": invalid_npis == 0,
        "require_valid_hcpcs_code": invalid_hcpcs == 0,
        "require_allowed_dimension_domains": invalid_domains == 0,
        "retain_all_reporting_years": years
        == contract["allowed_values"]["reporting_years"],
        "require_canonical_source_schema": schema_valid,
        "reject_unparseable_numeric_values": True,
        "require_integral_beneficiary_counts": fractional_benes == 0,
        "require_integral_beneficiary_day_services": fractional_days == 0,
        "preserve_fractional_total_services": fractional_services
        == contract["numeric_typing"]["observed_fractional_service_rows"],
        "require_published_beneficiary_minimum": below_minimum == 0,
        "require_nonnegative_measures": negative_measures == 0,
        "require_medicare_payment_not_above_allowed_amount": (
            payment_above_allowed == 0
        ),
        "report_allowed_above_submitted_charge": True,
        "report_payment_above_submitted_charge": True,
        "report_standardized_above_allowed_amount": True,
        "require_nullable_dimension_policy": missing_state_fips
        == contract["nullable_dimension_policy"]["provider_state_fips"][
            "observed_null_or_blank_rows"
        ]
        and missing_ruca
        == contract["nullable_dimension_policy"]["provider_ruca_code"][
            "observed_null_or_blank_rows"
        ],
        "require_year_specific_provider_attributes": contract[
            "historical_attribute_handling"
        ]["preserve_reported_values_by_year"],
        "require_year_specific_hcpcs_descriptions": contract[
            "hcpcs_description_handling"
        ]["preserve_reported_description_by_year"],
        "require_country_safe_peer_configuration": foreign_peer_violations == 0,
        "require_peer_group_threshold_configuration": contract["benchmark_cohorts"][
            "minimum_peer_group_size"
        ]
        >= 11,
        "prohibit_real_provider_anomaly_attribution": not contract[
            "privacy_and_reporting"
        ]["expose_real_provider_anomaly_flags"],
    }
    if set(checks) != set(contract["quality_rules"]):
        raise PhysicianServiceSilverError(
            "Implemented checks do not match contract rules"
        )
    return {
        "quality_report_version": 1,
        "model_name": contract["model"]["name"],
        "data_role": contract["model"]["data_role"],
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measures),
        "reporting_years": years,
        "fractional_total_service_count": fractional_services,
        "missing_state_fips_count": missing_state_fips,
        "missing_ruca_code_count": missing_ruca,
        "observed_relationship_counts": {
            "allowed_above_submitted_charge": allowed_above_charge,
            "payment_above_submitted_charge": payment_above_charge,
            "standardized_above_allowed": standardized_above_allowed,
        },
        "violation_counts": {
            "duplicate_business_keys": duplicate_keys,
            "null_business_keys": null_keys,
            "invalid_npis": invalid_npis,
            "invalid_hcpcs_codes": invalid_hcpcs,
            "invalid_dimension_domains": invalid_domains,
            "fractional_beneficiary_counts": fractional_benes,
            "fractional_beneficiary_day_services": fractional_days,
            "below_publication_minimum": below_minimum,
            "negative_measures": negative_measures,
            "medicare_payment_above_allowed_amount": payment_above_allowed,
            "foreign_peer_violations": foreign_peer_violations,
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_physician_service_silver(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    paths = contract["paths"]
    bronze_glob = paths["bronze_glob"]
    silver_path = Path(paths["silver_output"])
    partial_path = silver_path.with_suffix(".parquet.partial")
    quality_path = Path(paths["quality_report"])
    silver_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path.unlink(missing_ok=True)
    try:
        with duckdb.connect() as connection:
            source_columns = parquet_columns(connection, bronze_glob)
            query, measures = silver_sql(source_columns, contract, bronze_glob)
            invalid_values = invalid_numeric_count(
                connection, bronze_glob, measures, contract
            )
            if invalid_values:
                raise PhysicianServiceSilverError(
                    f"Unparseable numeric values found: {invalid_values}"
                )
            connection.execute(
                f"COPY ({query}) TO {sql_literal(str(partial_path))} "
                "(FORMAT PARQUET, COMPRESSION ZSTD)"
            )
            report = quality_report(
                connection,
                bronze_glob,
                partial_path,
                source_columns,
                measures,
                contract,
            )
        quality_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if not report["all_checks_passed"]:
            raise PhysicianServiceSilverError(
                f"Silver quality checks failed; see {quality_path}"
            )
        partial_path.replace(silver_path)
        return report
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the governed CMS physician-service Silver model."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    return parser.parse_args()


def main() -> None:
    report = build_physician_service_silver(parse_args().contract)
    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(f"Fractional total-service rows: {report['fractional_total_service_count']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
