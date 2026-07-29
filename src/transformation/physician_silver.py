from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.transformation.geographic_silver import (
    quote_identifier,
    sql_literal,
)

DEFAULT_CONTRACT_PATH = Path("config/physician_silver.yml")


class PhysicianSilverError(RuntimeError):
    """Raised when physician bronze data cannot satisfy the silver contract."""


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    """Load the governed physician silver contract."""
    if not path.exists():
        raise PhysicianSilverError(f"Physician silver contract does not exist: {path}")

    contract = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(contract, dict):
        raise PhysicianSilverError("Physician silver contract must contain a mapping")

    return contract


def source_measure_columns(
    source_columns: list[str],
    contract: dict[str, Any],
) -> list[str]:
    """Return columns governed as physician analytical measures."""
    excluded = set(contract["numeric_typing"]["excluded_columns"])
    return [column for column in source_columns if column not in excluded]


def target_column_name(source_column: str) -> str:
    """Normalize a CMS source column to its silver name."""
    return source_column.lower()


def measure_type(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Resolve the governed silver type for a numeric measure."""
    numeric_typing = contract["numeric_typing"]

    if source_column in numeric_typing["integer_columns"]:
        return numeric_typing["integer_type"]

    return numeric_typing["decimal_type"]


def normalized_measure_expression(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Create a typed measure expression without imputing missing values."""
    source_sql = quote_identifier(source_column)
    target_sql = quote_identifier(target_column_name(source_column))
    target_type = measure_type(source_column, contract)

    return f"TRY_CAST(TRIM({source_sql}) AS {target_type}) AS {target_sql}"


def suppression_status_expression(
    indicator_column: str,
    contract: dict[str, Any],
) -> str:
    """Translate an official CMS suppression indicator to a status."""
    statuses = contract["suppression"]["statuses"]
    source_sql = quote_identifier(indicator_column)
    indicator_settings = contract["suppression"]["indicators"][indicator_column]
    target_name = f"{indicator_settings['target_group']}_suppression_status"

    clauses = " ".join(
        f"WHEN {source_sql} = {sql_literal(token)} THEN {sql_literal(status)}"
        for token, status in statuses.items()
    )

    return (
        f"CASE {clauses} ELSE 'not_suppressed' END AS {quote_identifier(target_name)}"
    )


def top_coded_indicator_expression(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Identify chronic-condition percentages reported at the CMS cap."""
    source_sql = quote_identifier(source_column)
    target_type = contract["numeric_typing"]["decimal_type"]
    upper_bound = contract["top_coding"]["upper_bound"]
    target_name = f"{target_column_name(source_column)}_is_top_coded"

    return (
        f"CASE WHEN TRY_CAST(TRIM({source_sql}) AS {target_type}) "
        f"= {upper_bound} THEN TRUE ELSE FALSE END "
        f"AS {quote_identifier(target_name)}"
    )


def provider_size_band_expression(
    contract: dict[str, Any],
) -> str:
    """Build the contract-driven provider-size classification."""
    cohorts = contract["benchmark_cohorts"]
    measure_sql = quote_identifier(cohorts["provider_size_measure"])
    clauses: list[str] = []

    for band in cohorts["provider_size_bands"]:
        minimum = band["minimum_inclusive"]
        maximum = band["maximum_inclusive"]
        name = sql_literal(band["name"])

        if maximum is None:
            condition = f"{measure_sql} >= {minimum}"
        else:
            condition = f"{measure_sql} BETWEEN {minimum} AND {maximum}"

        clauses.append(f"WHEN {condition} THEN {name}")

    return "CASE " + " ".join(clauses) + " ELSE NULL END AS provider_size_band"
