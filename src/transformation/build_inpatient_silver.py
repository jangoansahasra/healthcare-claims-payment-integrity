from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import quote_identifier, sql_literal
from src.transformation.inpatient_silver import (
    DEFAULT_CONTRACT_PATH,
    InpatientSilverError,
    discharge_volume_band_expression,
    load_contract,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    source_measure_columns,
    total_payment_above_charge_expression,
)


def scalar_count(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any],
) -> int:
    return int(connection.execute(query, parameters).fetchone()[0])


def parquet_columns(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
) -> list[str]:
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
    source_columns: list[str],
    contract: dict[str, Any],
    bronze_glob: str,
) -> tuple[str, list[str]]:
    required = set(contract["source_dimensions"])
    required.update(contract["retained_lineage"])
    required.update(contract["source_schema"]["required_columns"])
    missing = sorted(required - set(source_columns))
    if missing:
        raise InpatientSilverError(
            "Missing required source columns: " + ", ".join(missing)
        )

    measures = source_measure_columns(source_columns, contract)
    governed = [
        *contract["numeric_typing"]["integer_columns"],
        *contract["numeric_typing"]["decimal_columns"],
    ]
    if measures != governed:
        raise InpatientSilverError(
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
    inner_expressions = [
        *dimensions,
        *missing_indicators,
        "CAST(_reporting_year AS INTEGER) AS reporting_year",
        *[normalized_measure_expression(column, contract) for column in measures],
        *contract["retained_lineage"],
    ]
    inner = (
        "SELECT\n  "
        + ",\n  ".join(inner_expressions)
        + "\nFROM read_parquet("
        + sql_literal(bronze_glob)
        + ")"
    )
    outer_expressions = [
        "*",
        discharge_volume_band_expression(contract),
        total_payment_above_charge_expression(),
    ]
    return (
        "SELECT\n  "
        + ",\n  ".join(outer_expressions)
        + "\nFROM (\n"
        + inner
        + "\n) typed",
        measures,
    )


def create_quality_report(
    connection: duckdb.DuckDBPyConnection,
    bronze_glob: str,
    silver_path: Path,
    source_columns: list[str],
    measures: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
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
        SELECT COUNT(*) FROM (
            SELECT hospital_ccn, ms_drg_code, reporting_year
            FROM read_parquet(?)
            GROUP BY 1, 2, 3
            HAVING COUNT(*) > 1
        )
        """,
        [str(silver_path)],
    )
    null_keys = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE hospital_ccn IS NULL
           OR ms_drg_code IS NULL
           OR reporting_year IS NULL
        """,
        [str(silver_path)],
    )

    def pattern_violations(column: str, pattern: str) -> int:
        return scalar_count(
            connection,
            f"""
            SELECT COUNT(*) FROM read_parquet(?)
            WHERE {quote_identifier(column)} IS NULL
               OR NOT regexp_full_match(
                    {quote_identifier(column)}, ?
               )
            """,
            [str(silver_path), pattern.removeprefix("^").removesuffix("$")],
        )

    allowed = contract["allowed_values"]
    invalid_ccns = pattern_violations("hospital_ccn", allowed["ccn_pattern"])
    invalid_drgs = pattern_violations("ms_drg_code", allowed["ms_drg_pattern"])
    invalid_state_fips = pattern_violations(
        "hospital_state_fips", allowed["state_fips_pattern"]
    )
    invalid_zip5 = pattern_violations("hospital_zip5", allowed["zip5_pattern"])
    years = [
        int(row[0])
        for row in connection.execute(
            "SELECT DISTINCT reporting_year FROM read_parquet(?) ORDER BY 1",
            [str(silver_path)],
        ).fetchall()
    ]

    fractional_discharges = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE TRY_CAST(Tot_Dschrgs AS DECIMAL(38,6))
           <> TRUNC(TRY_CAST(Tot_Dschrgs AS DECIMAL(38,6)))
        """,
        [bronze_glob],
    )
    below_publication_minimum = scalar_count(
        connection,
        "SELECT COUNT(*) FROM read_parquet(?) WHERE total_discharges < ?",
        [
            str(silver_path),
            contract["publication_threshold"]["minimum_published_value"],
        ],
    )
    negative_discharges = scalar_count(
        connection,
        "SELECT COUNT(*) FROM read_parquet(?) WHERE total_discharges < 0",
        [str(silver_path)],
    )
    negative_financial = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE average_submitted_covered_charge < 0
           OR average_total_payment < 0
           OR average_medicare_payment < 0
        """,
        [str(silver_path)],
    )
    medicare_above_total = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE average_medicare_payment > average_total_payment
        """,
        [str(silver_path)],
    )
    total_above_charge = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE total_payment_above_covered_charge
        """,
        [str(silver_path)],
    )
    missing_ruca_codes = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE hospital_ruca_code_is_missing
        """,
        [str(silver_path)],
    )
    missing_ruca_descriptions = scalar_count(
        connection,
        """
        SELECT COUNT(*) FROM read_parquet(?)
        WHERE hospital_ruca_description_is_missing
        """,
        [str(silver_path)],
    )

    cms_columns = set(source_columns) - set(contract["retained_lineage"])
    schema_valid = (
        len(cms_columns) == contract["source_schema"]["expected_cms_column_count"]
        and len(set(source_columns) - cms_columns)
        == contract["source_schema"]["expected_lineage_column_count"]
        and set(contract["source_schema"]["required_columns"]).issubset(cms_columns)
    )
    nullable_policy_valid = (
        contract["nullable_dimension_policy"]["hospital_ruca_code"][
            "preserve_missing_indicator"
        ]
        and contract["nullable_dimension_policy"]["hospital_ruca_description"][
            "preserve_missing_indicator"
        ]
        and missing_ruca_codes == missing_ruca_descriptions
    )
    checks = {
        "preserve_source_row_count": bronze_rows == silver_rows,
        "require_unique_business_key": duplicate_keys == 0,
        "require_non_null_business_key": null_keys == 0,
        "require_valid_ccn": invalid_ccns == 0,
        "require_valid_ms_drg_code": invalid_drgs == 0,
        "require_valid_state_fips": invalid_state_fips == 0,
        "require_valid_zip5": invalid_zip5 == 0,
        "retain_all_reporting_years": years
        == contract["allowed_values"]["reporting_years"],
        "require_canonical_source_schema": schema_valid,
        "reject_unparseable_numeric_values": True,
        "require_integral_discharges": fractional_discharges == 0,
        "require_published_discharge_minimum": below_publication_minimum == 0,
        "require_nonnegative_discharges": negative_discharges == 0,
        "require_nonnegative_financial_values": negative_financial == 0,
        "require_medicare_payment_not_above_total_payment": (medicare_above_total == 0),
        "report_total_payment_above_covered_charge": True,
        "require_nullable_dimension_policy": nullable_policy_valid,
        "require_year_specific_hospital_attributes": contract[
            "historical_attribute_handling"
        ]["preserve_reported_values_by_year"],
        "require_year_specific_drg_descriptions": contract["drg_description_handling"][
            "preserve_reported_description_by_year"
        ],
        "require_peer_group_threshold_configuration": contract["benchmark_cohorts"][
            "minimum_peer_group_size"
        ]
        >= 11,
        "prohibit_real_hospital_anomaly_attribution": not contract[
            "privacy_and_reporting"
        ]["expose_real_hospital_anomaly_flags"],
    }
    violations = {
        "duplicate_business_keys": duplicate_keys,
        "null_business_keys": null_keys,
        "invalid_ccns": invalid_ccns,
        "invalid_ms_drg_codes": invalid_drgs,
        "invalid_state_fips": invalid_state_fips,
        "invalid_zip5": invalid_zip5,
        "fractional_discharges": fractional_discharges,
        "below_publication_minimum": below_publication_minimum,
        "negative_discharges": negative_discharges,
        "negative_financial_values": negative_financial,
        "medicare_payment_above_total_payment": medicare_above_total,
    }
    return {
        "quality_report_version": 1,
        "model_name": contract["model"]["name"],
        "data_role": contract["model"]["data_role"],
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measures),
        "reporting_years": years,
        "missing_ruca_code_count": missing_ruca_codes,
        "missing_ruca_description_count": missing_ruca_descriptions,
        "total_payment_above_covered_charge_count": total_above_charge,
        "violation_counts": violations,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_inpatient_silver(
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
        silver_sql, measures = silver_select_sql(
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
            raise InpatientSilverError(
                f"Unparseable numeric values found: {invalid_values}"
            )

        connection.execute(
            f"""
            COPY ({silver_sql})
            TO {sql_literal(str(silver_path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
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
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not report["all_checks_passed"]:
        raise InpatientSilverError(
            f"Inpatient Silver quality checks failed; see {quality_path}"
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the governed CMS inpatient Silver model."
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT_PATH,
    )
    return parser.parse_args()


def main() -> None:
    report = build_inpatient_silver(parse_args().contract)
    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(
        "Total payment above covered charge rows: "
        f"{report['total_payment_above_covered_charge_count']}"
    )
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
