from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.transformation.geographic_silver import (
    quote_identifier,
    sql_literal,
)

DEFAULT_CONTRACT_PATH = Path("config/part_d_silver.yml")


class PartDSilverError(RuntimeError):
    """Raised when Part D bronze data cannot satisfy its contract."""


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    """Load the governed Part D silver contract."""
    if not path.exists():
        raise PartDSilverError(f"Part D silver contract does not exist: {path}")

    contract = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(contract, dict):
        raise PartDSilverError("Part D silver contract must contain a mapping")

    return contract


def source_measure_columns(
    source_columns: list[str],
    contract: dict[str, Any],
) -> list[str]:
    """Return source columns governed as analytical measures."""
    excluded = set(contract["numeric_typing"]["excluded_columns"])
    return [column for column in source_columns if column not in excluded]


def target_column_name(source_column: str) -> str:
    """Normalize a CMS source column to its silver name."""
    return source_column.lower()


def decimal_measure_columns(
    contract: dict[str, Any],
) -> set[str]:
    """Return all measures governed as decimals."""
    return {
        column
        for columns in contract["numeric_typing"]["decimal_measure_classes"].values()
        for column in columns
    }


def measure_type(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Resolve the governed target type for one measure."""
    typing = contract["numeric_typing"]

    if source_column in typing["integer_columns"]:
        return typing["integer_type"]

    if source_column in decimal_measure_columns(contract):
        return typing["decimal_type"]

    raise PartDSilverError(f"Measure has no governed type: {source_column}")


def normalized_measure_expression(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Create a typed expression without imputing null values."""
    source_sql = quote_identifier(source_column)
    target_sql = quote_identifier(target_column_name(source_column))
    target_type = measure_type(
        source_column,
        contract,
    )

    return (
        f"TRY_CAST(TRIM(CAST({source_sql} AS VARCHAR)) "
        f"AS {target_type}) AS {target_sql}"
    )


def normalized_dimension_expression(
    source_column: str,
    target_column: str,
    contract: dict[str, Any],
) -> str:
    """Normalize a dimension using its governed null policy."""
    source_sql = quote_identifier(source_column)
    target_sql = quote_identifier(target_column)
    trimmed = f"NULLIF(TRIM(CAST({source_sql} AS VARCHAR)), '')"
    policy = contract["nullable_dimension_policy"].get(target_column)

    if policy and "silver_value_when_missing" in policy:
        unknown = sql_literal(policy["silver_value_when_missing"])
        return f"COALESCE({trimmed}, {unknown}) AS {target_sql}"

    return f"{trimmed} AS {target_sql}"


def missing_dimension_indicator_expression(
    source_column: str,
    target_column: str,
    contract: dict[str, Any],
) -> str:
    """Preserve whether a dimension was absent in the source."""
    policy = contract["nullable_dimension_policy"].get(target_column)

    if not policy or not policy.get("preserve_missing_indicator"):
        raise PartDSilverError(
            f"Dimension has no governed missing indicator: {target_column}"
        )

    source_sql = quote_identifier(source_column)
    target_sql = quote_identifier(f"{target_column}_is_missing")

    return (
        f"CASE WHEN {source_sql} IS NULL "
        f"OR TRIM(CAST({source_sql} AS VARCHAR)) = '' "
        f"THEN TRUE ELSE FALSE END AS {target_sql}"
    )


def suppression_status_expression(
    indicator_column: str,
    contract: dict[str, Any],
) -> str:
    """Translate one official CMS suppression flag."""
    suppression = contract["suppression"]
    settings = suppression["indicators"][indicator_column]
    source_sql = f"TRIM(CAST({quote_identifier(indicator_column)} AS VARCHAR))"
    target_sql = quote_identifier(f"{settings['target_group']}_suppression_status")

    clauses = " ".join(
        f"WHEN {source_sql} = {sql_literal(token)} "
        f"THEN {sql_literal(suppression['statuses'][token])}"
        for token in settings["allowed_tokens"]
    )

    return f"CASE {clauses} ELSE 'not_suppressed' END AS {target_sql}"


def prescriber_size_band_expression(
    contract: dict[str, Any],
) -> str:
    """Build the contract-driven claim-volume band."""
    settings = contract["prescriber_size_bands"]
    measure_sql = quote_identifier(settings["measure"])
    clauses: list[str] = []

    for band in settings["bands"]:
        minimum = band["minimum_inclusive"]
        maximum = band["maximum_inclusive"]
        name = sql_literal(band["name"])

        if maximum is None:
            condition = f"{measure_sql} >= {minimum}"
        else:
            condition = f"{measure_sql} BETWEEN {minimum} AND {maximum}"

        clauses.append(f"WHEN {condition} THEN {name}")

    return "CASE " + " ".join(clauses) + " ELSE NULL END AS prescriber_size_band"
