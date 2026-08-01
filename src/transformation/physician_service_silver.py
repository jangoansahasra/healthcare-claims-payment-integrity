from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.transformation.geographic_silver import quote_identifier, sql_literal

DEFAULT_CONTRACT_PATH = Path("config/physician_service_silver.yml")

MEASURE_TARGETS = {
    "Tot_Benes": "total_beneficiaries",
    "Tot_Srvcs": "total_services",
    "Tot_Bene_Day_Srvcs": "total_beneficiary_day_services",
    "Avg_Sbmtd_Chrg": "average_submitted_charge",
    "Avg_Mdcr_Alowd_Amt": "average_medicare_allowed_amount",
    "Avg_Mdcr_Pymt_Amt": "average_medicare_payment",
    "Avg_Mdcr_Stdzd_Amt": "average_standardized_medicare_payment",
}


class PhysicianServiceSilverError(RuntimeError):
    """Raised when physician-service Bronze data cannot satisfy its contract."""


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    if not path.exists():
        raise PhysicianServiceSilverError(f"Silver contract does not exist: {path}")
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise PhysicianServiceSilverError("Silver contract must contain a mapping")
    return contract


def source_measure_columns(
    source_columns: list[str], contract: dict[str, Any]
) -> list[str]:
    governed = set(contract["numeric_typing"]["integer_columns"])
    governed.update(contract["numeric_typing"]["decimal_columns"])
    return [column for column in source_columns if column in governed]


def target_column_name(source_column: str) -> str:
    try:
        return MEASURE_TARGETS[source_column]
    except KeyError as error:
        raise PhysicianServiceSilverError(
            f"Measure has no governed target: {source_column}"
        ) from error


def measure_type(source_column: str, contract: dict[str, Any]) -> str:
    typing = contract["numeric_typing"]
    if source_column in typing["integer_columns"]:
        return typing["integer_type"]
    if source_column in typing["decimal_columns"]:
        return typing["decimal_type"]
    raise PhysicianServiceSilverError(f"Measure has no governed type: {source_column}")


def normalized_measure_expression(source_column: str, contract: dict[str, Any]) -> str:
    source = quote_identifier(source_column)
    target = quote_identifier(target_column_name(source_column))
    return (
        f"TRY_CAST(TRIM(CAST({source} AS VARCHAR)) AS "
        f"{measure_type(source_column, contract)}) AS {target}"
    )


def normalized_dimension_expression(
    source_column: str, target_column: str, contract: dict[str, Any]
) -> str:
    """Normalize a dimension under its explicit missing-value policy."""
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
    source_column: str, target_column: str, contract: dict[str, Any]
) -> str:
    policy = contract["nullable_dimension_policy"].get(target_column)
    if not policy or not policy.get("preserve_missing_indicator"):
        raise PhysicianServiceSilverError(
            f"Dimension has no governed missing indicator: {target_column}"
        )
    source = quote_identifier(source_column)
    target = quote_identifier(f"{target_column}_is_missing")
    return (
        f"CASE WHEN {source} IS NULL OR TRIM(CAST({source} AS VARCHAR)) = '' "
        f"THEN TRUE ELSE FALSE END AS {target}"
    )


def beneficiary_volume_band_expression(contract: dict[str, Any]) -> str:
    settings = contract["beneficiary_volume_bands"]
    measure = quote_identifier(settings["measure"])
    clauses = []
    for band in settings["bands"]:
        minimum = band["minimum_inclusive"]
        maximum = band["maximum_inclusive"]
        condition = (
            f"{measure} >= {minimum}"
            if maximum is None
            else f"{measure} BETWEEN {minimum} AND {maximum}"
        )
        clauses.append(f"WHEN {condition} THEN {sql_literal(band['name'])}")
    return "CASE " + " ".join(clauses) + " ELSE NULL END AS beneficiary_volume_band"
