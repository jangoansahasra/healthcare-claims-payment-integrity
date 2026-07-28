from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from src.transformation.geographic_silver import (
    SilverTransformationError,
    geography_identifier_expression,
    invalid_numeric_predicate,
    load_contract,
    measure_type,
    normalized_measure_expression,
    quote_identifier,
    source_measure_columns,
    sql_literal,
    target_measure_name,
)


def parquet_columns(
    connection: duckdb.DuckDBPyConnection,
    parquet_path: Path,
) -> list[str]:
    rows = connection.execute(
        "DESCRIBE SELECT * FROM read_parquet(?)",
        [str(parquet_path)],
    ).fetchall()
    return [row[0] for row in rows]


def invalid_numeric_values(
    connection: duckdb.DuckDBPyConnection,
    bronze_path: Path,
    measure_columns: list[str],
    contract: dict[str, Any],
) -> list[dict[str, Any]]:
    expressions = [
        (
            "SUM(CASE WHEN "
            f"{invalid_numeric_predicate(column, contract)} "
            "THEN 1 ELSE 0 END) "
            f"AS {quote_identifier(column)}"
        )
        for column in measure_columns
    ]

    counts = connection.execute(
        "SELECT "
        + ", ".join(expressions)
        + f" FROM read_parquet({sql_literal(str(bronze_path))})"
    ).fetchone()

    return [
        {"measure_name": column, "invalid_row_count": count}
        for column, count in zip(measure_columns, counts, strict=True)
        if count
    ]


def special_value_count_expression(
    measure_columns: list[str],
    tokens: list[str],
    alias: str,
) -> str:
    token_sql = ", ".join(sql_literal(token) for token in tokens)
    expressions = [
        (
            "CASE WHEN "
            f"TRIM({quote_identifier(column)}) IN ({token_sql}) "
            "THEN 1 ELSE 0 END"
        )
        for column in measure_columns
    ]

    return " + ".join(expressions) + f" AS {quote_identifier(alias)}"


def silver_select_sql(
    bronze_path: Path,
    measure_columns: list[str],
    contract: dict[str, Any],
) -> str:
    dimensions = [
        "TRY_CAST(YEAR AS INTEGER) AS year",
        "BENE_GEO_LVL AS geography_level",
        geography_identifier_expression(contract),
        "BENE_GEO_DESC AS geography_name",
        "BENE_GEO_CD AS source_geography_code",
        "BENE_AGE_LVL AS beneficiary_age_level",
    ]
    measures = [
        normalized_measure_expression(column, contract) for column in measure_columns
    ]
    special_values = contract["special_values"]
    status_counts = [
        special_value_count_expression(
            measure_columns,
            special_values["suppression_tokens"],
            "suppressed_measure_count",
        ),
        special_value_count_expression(
            measure_columns,
            special_values["not_applicable_tokens"],
            "not_applicable_measure_count",
        ),
    ]
    lineage = [
        "_source_id",
        "_reporting_year",
        "_source_file",
        "_acquired_at_utc",
    ]

    return (
        "SELECT\n    "
        + ",\n    ".join([*dimensions, *measures, *status_counts, *lineage])
        + f"\nFROM read_parquet({sql_literal(str(bronze_path))})"
    )


def value_status_select_sql(
    bronze_path: Path,
    measure_columns: list[str],
    contract: dict[str, Any],
) -> str:
    quoted_measures = ", ".join(quote_identifier(column) for column in measure_columns)
    source_projection = ", ".join(
        [
            "YEAR",
            "BENE_GEO_LVL",
            "BENE_GEO_DESC",
            "BENE_GEO_CD",
            "BENE_AGE_LVL",
            quoted_measures,
        ]
    )
    special_values = contract["special_values"]
    suppression_sql = ", ".join(
        sql_literal(token) for token in special_values["suppression_tokens"]
    )
    not_applicable_sql = ", ".join(
        sql_literal(token) for token in special_values["not_applicable_tokens"]
    )
    governed_tokens = ", ".join(
        [
            suppression_sql,
            not_applicable_sql,
        ]
    )

    return f"""
        SELECT
            TRY_CAST(YEAR AS INTEGER) AS year,
            BENE_GEO_LVL AS geography_level,
            {geography_identifier_expression(contract)},
            BENE_AGE_LVL AS beneficiary_age_level,
            LOWER(measure_name) AS measure_name,
            source_token,
            CASE
                WHEN TRIM(source_token) IN ({suppression_sql})
                    THEN 'suppressed'
                WHEN TRIM(source_token) IN ({not_applicable_sql})
                    THEN 'not_applicable'
            END AS value_status
        FROM (
            UNPIVOT (
                SELECT {source_projection}
                FROM read_parquet({sql_literal(str(bronze_path))})
            )
            ON {quoted_measures}
            INTO NAME measure_name VALUE source_token
        )
        WHERE TRIM(source_token) IN ({governed_tokens})
    """


def range_violation_count(
    connection: duckdb.DuckDBPyConnection,
    parquet_path: Path,
    columns: list[str],
    minimum: int | float | None = None,
    maximum: int | float | None = None,
) -> int:
    predicates: list[str] = []

    for column in columns:
        quoted = quote_identifier(target_measure_name(column))
        bounds: list[str] = []

        if minimum is not None:
            bounds.append(f"{quoted} < {minimum}")
        if maximum is not None:
            bounds.append(f"{quoted} > {maximum}")

        predicates.append("(" + " OR ".join(bounds) + ")")

    if not predicates:
        return 0

    return connection.execute(
        "SELECT COUNT(*) "
        f"FROM read_parquet({sql_literal(str(parquet_path))}) "
        "WHERE " + " OR ".join(predicates)
    ).fetchone()[0]


def create_quality_report(
    connection: duckdb.DuckDBPyConnection,
    bronze_path: Path,
    silver_path: Path,
    value_status_path: Path,
    measure_columns: list[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    bronze_rows = connection.execute(
        f"SELECT COUNT(*) FROM read_parquet({sql_literal(str(bronze_path))})"
    ).fetchone()[0]
    silver_rows = connection.execute(
        f"SELECT COUNT(*) FROM read_parquet({sql_literal(str(silver_path))})"
    ).fetchone()[0]

    duplicate_keys = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM (
            SELECT
                year,
                geography_level,
                geography_id,
                beneficiary_age_level,
                COUNT(*) AS row_count
            FROM read_parquet({sql_literal(str(silver_path))})
            GROUP BY 1, 2, 3, 4
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]

    null_keys = connection.execute(
        f"""
        SELECT COUNT(*)
        FROM read_parquet({sql_literal(str(silver_path))})
        WHERE year IS NULL
           OR geography_level IS NULL
           OR geography_id IS NULL
           OR beneficiary_age_level IS NULL
        """
    ).fetchone()[0]

    years = [
        row[0]
        for row in connection.execute(
            f"""
            SELECT DISTINCT year
            FROM read_parquet({sql_literal(str(silver_path))})
            ORDER BY year
            """
        ).fetchall()
    ]
    geography_levels = [
        row[0]
        for row in connection.execute(
            f"""
            SELECT DISTINCT geography_level
            FROM read_parquet({sql_literal(str(silver_path))})
            ORDER BY geography_level
            """
        ).fetchall()
    ]
    age_levels = [
        row[0]
        for row in connection.execute(
            f"""
            SELECT DISTINCT beneficiary_age_level
            FROM read_parquet({sql_literal(str(silver_path))})
            ORDER BY beneficiary_age_level
            """
        ).fetchall()
    ]
    status_counts = {
        row[0]: row[1]
        for row in connection.execute(
            f"""
            SELECT value_status, COUNT(*)
            FROM read_parquet({sql_literal(str(value_status_path))})
            GROUP BY value_status
            ORDER BY value_status
            """
        ).fetchall()
    }

    count_columns = [
        column
        for column in measure_columns
        if measure_type(column, contract) == contract["measure_typing"]["integer_type"]
    ]
    payment_columns = [
        column
        for column in measure_columns
        if "PYMT" in column and column.endswith("_AMT")
    ]
    percentage_columns = [
        column for column in measure_columns if column.endswith(("_PCT", "_RATE"))
    ]

    count_range_violations = range_violation_count(
        connection,
        silver_path,
        count_columns,
        minimum=0,
    )
    payment_range_violations = range_violation_count(
        connection,
        silver_path,
        payment_columns,
        minimum=0,
    )
    percentage_range_violations = range_violation_count(
        connection,
        silver_path,
        percentage_columns,
        minimum=0,
        maximum=100,
    )

    allowed = contract["allowed_values"]
    expected_years = list(range(allowed["minimum_year"], allowed["maximum_year"] + 1))
    expected_geographies = sorted(allowed["geography_level"])
    expected_age_levels = sorted(allowed["beneficiary_age_level"])

    checks = {
        "source_row_count_preserved": bronze_rows == silver_rows,
        "business_key_unique": duplicate_keys == 0,
        "business_key_non_null": null_keys == 0,
        "source_years_retained": years == expected_years,
        "geography_levels_retained": (geography_levels == expected_geographies),
        "age_levels_retained": age_levels == expected_age_levels,
        "counts_nonnegative": count_range_violations == 0,
        "payment_amounts_nonnegative": payment_range_violations == 0,
        "percentages_in_range": percentage_range_violations == 0,
    }

    return {
        "quality_report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "model_name": contract["model"]["name"],
        "source_id": contract["model"]["source_id"],
        "bronze_path": str(bronze_path),
        "silver_path": str(silver_path),
        "value_status_path": str(value_status_path),
        "bronze_row_count": bronze_rows,
        "silver_row_count": silver_rows,
        "measure_count": len(measure_columns),
        "duplicate_business_key_count": duplicate_keys,
        "null_business_key_count": null_keys,
        "years": years,
        "geography_levels": geography_levels,
        "beneficiary_age_levels": age_levels,
        "special_value_counts": status_counts,
        "range_violation_counts": {
            "counts": count_range_violations,
            "payment_amounts": payment_range_violations,
            "percentages": percentage_range_violations,
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }


def build_geographic_silver(
    contract_path: Path,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    paths = contract["paths"]
    bronze_path = Path(paths["bronze_input"])
    silver_path = Path(paths["silver_output"])
    value_status_path = Path(paths["value_status_output"])
    quality_report_path = Path(paths["quality_report"])

    if not bronze_path.exists():
        raise SilverTransformationError(f"Bronze input does not exist: {bronze_path}")

    silver_path.parent.mkdir(parents=True, exist_ok=True)
    value_status_path.parent.mkdir(parents=True, exist_ok=True)
    quality_report_path.parent.mkdir(parents=True, exist_ok=True)

    with duckdb.connect() as connection:
        columns = parquet_columns(connection, bronze_path)
        measures = source_measure_columns(columns, contract)
        invalid_values = invalid_numeric_values(
            connection,
            bronze_path,
            measures,
            contract,
        )

        if invalid_values:
            raise SilverTransformationError(
                "Ungoverned numeric values detected: " + json.dumps(invalid_values[:10])
            )

        for output_path in [silver_path, value_status_path]:
            if output_path.exists():
                output_path.unlink()

        connection.execute(
            f"""
            COPY ({silver_select_sql(bronze_path, measures, contract)})
            TO {sql_literal(str(silver_path))}
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD,
                ROW_GROUP_SIZE 100000
            )
            """
        )
        connection.execute(
            f"""
            COPY ({
                value_status_select_sql(
                    bronze_path,
                    measures,
                    contract,
                )
            })
            TO {sql_literal(str(value_status_path))}
            (
                FORMAT PARQUET,
                COMPRESSION ZSTD,
                ROW_GROUP_SIZE 100000
            )
            """
        )

        report = create_quality_report(
            connection,
            bronze_path,
            silver_path,
            value_status_path,
            measures,
            contract,
        )

    quality_report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if not report["all_checks_passed"]:
        raise SilverTransformationError(
            f"Silver quality checks failed; see {quality_report_path}"
        )

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the typed CMS Geographic Variation silver model."
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path("config/geographic_silver.yml"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_geographic_silver(args.contract)

    print(f"Silver rows: {report['silver_row_count']}")
    print(f"Typed measures: {report['measure_count']}")
    print(
        "Special values: " + json.dumps(report["special_value_counts"], sort_keys=True)
    )
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
