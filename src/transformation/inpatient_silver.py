from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.transformation.geographic_silver import quote_identifier, sql_literal

DEFAULT_CONTRACT_PATH = Path("config/inpatient_silver.yml")

MEASURE_TARGETS = {
    "Tot_Dschrgs": "total_discharges",
    "Avg_Submtd_Cvrd_Chrg": "average_submitted_covered_charge",
    "Avg_Tot_Pymt_Amt": "average_total_payment",
    "Avg_Mdcr_Pymt_Amt": "average_medicare_payment",
}


class InpatientSilverError(RuntimeError):
    """Raised when inpatient Bronze data cannot satisfy its contract."""


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    """Load the governed inpatient Silver contract."""
    if not path.exists():
        raise InpatientSilverError(f"Inpatient Silver contract does not exist: {path}")

    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise InpatientSilverError("Inpatient Silver contract must contain a mapping")
    return contract


def source_measure_columns(
    source_columns: list[str],
    contract: dict[str, Any],
) -> list[str]:
    """Return source columns governed as analytical measures."""
    governed = set(contract["numeric_typing"]["integer_columns"])
    governed.update(contract["numeric_typing"]["decimal_columns"])
    return [column for column in source_columns if column in governed]


def target_column_name(source_column: str) -> str:
    """Return the semantic Silver name for a source measure."""
    try:
        return MEASURE_TARGETS[source_column]
    except KeyError as error:
        raise InpatientSilverError(
            f"Measure has no governed target: {source_column}"
        ) from error


def measure_type(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Resolve the governed target type for a measure."""
    typing = contract["numeric_typing"]
    if source_column in typing["integer_columns"]:
        return typing["integer_type"]
    if source_column in typing["decimal_columns"]:
        return typing["decimal_type"]
    raise InpatientSilverError(f"Measure has no governed type: {source_column}")


def normalized_measure_expression(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Create a typed expression without imputing source nulls."""
    source = quote_identifier(source_column)
    target = quote_identifier(target_column_name(source_column))
    target_type = measure_type(source_column, contract)
    return f"TRY_CAST(TRIM(CAST({source} AS VARCHAR)) AS {target_type}) AS {target}"


def normalized_dimension_expression(
    source_column: str,
    target_column: str,
    contract: dict[str, Any],
) -> str:
    """Normalize a dimension under its explicit null policy."""
    source = quote_identifier(source_column)
    target = quote_identifier(target_column)
    trimmed = f"NULLIF(TRIM(CAST({source} AS VARCHAR)), '')"
    policy = contract["nullable_dimension_policy"].get(target_column)

    if policy and "silver_value_when_missing" in policy:
        return (
            f"COALESCE({trimmed}, "
            f"{sql_literal(policy['silver_value_when_missing'])}) AS {target}"
        )
    return f"{trimmed} AS {target}"


def missing_dimension_indicator_expression(
    source_column: str,
    target_column: str,
    contract: dict[str, Any],
) -> str:
    """Preserve whether a nullable dimension was absent in Bronze."""
    policy = contract["nullable_dimension_policy"].get(target_column)
    if not policy or not policy.get("preserve_missing_indicator"):
        raise InpatientSilverError(
            f"Dimension has no governed missing indicator: {target_column}"
        )

    source = quote_identifier(source_column)
    target = quote_identifier(f"{target_column}_is_missing")
    return (
        f"CASE WHEN {source} IS NULL "
        f"OR TRIM(CAST({source} AS VARCHAR)) = '' "
        f"THEN TRUE ELSE FALSE END AS {target}"
    )


def discharge_volume_band_expression(
    contract: dict[str, Any],
) -> str:
    """Build the contract-driven discharge-volume band."""
    settings = contract["discharge_volume_bands"]
    measure = quote_identifier(settings["measure"])
    clauses = []

    for band in settings["bands"]:
        minimum = band["minimum_inclusive"]
        maximum = band["maximum_inclusive"]
        if maximum is None:
            condition = f"{measure} >= {minimum}"
        else:
            condition = f"{measure} BETWEEN {minimum} AND {maximum}"
        clauses.append(f"WHEN {condition} THEN {sql_literal(band['name'])}")

    return "CASE " + " ".join(clauses) + " ELSE NULL END AS discharge_volume_band"


def total_payment_above_charge_expression() -> str:
    """Flag an observed payment/charge relationship without rejecting it."""
    return (
        'CASE WHEN "average_total_payment" > '
        '"average_submitted_covered_charge" '
        "THEN TRUE ELSE FALSE END "
        "AS total_payment_above_covered_charge"
    )
