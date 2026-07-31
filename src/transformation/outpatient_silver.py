from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.transformation.geographic_silver import quote_identifier, sql_literal

DEFAULT_CONTRACT_PATH = Path("config/outpatient_silver.yml")

MEASURE_TARGETS = {
    "Bene_Cnt": "beneficiary_count",
    "CAPC_Srvcs": "comprehensive_apc_services",
    "Avg_Tot_Sbmtd_Chrgs": "average_submitted_charge",
    "Avg_Mdcr_Alowd_Amt": "average_medicare_allowed_amount",
    "Avg_Mdcr_Pymt_Amt": "average_medicare_payment",
    "Outlier_Srvcs": "outlier_services",
    "Avg_Mdcr_Outlier_Amt": "average_medicare_outlier_amount",
}


class OutpatientSilverError(RuntimeError):
    """Raised when outpatient Bronze data cannot satisfy its contract."""


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    """Load the governed outpatient Silver contract."""
    if not path.exists():
        raise OutpatientSilverError(
            f"Outpatient Silver contract does not exist: {path}"
        )
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise OutpatientSilverError("Outpatient Silver contract must contain a mapping")
    return contract


def source_measure_columns(
    source_columns: list[str], contract: dict[str, Any]
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
        raise OutpatientSilverError(
            f"Measure has no governed target: {source_column}"
        ) from error


def measure_type(source_column: str, contract: dict[str, Any]) -> str:
    """Resolve the governed target type for a measure."""
    typing = contract["numeric_typing"]
    if source_column in typing["integer_columns"]:
        return typing["integer_type"]
    if source_column in typing["decimal_columns"]:
        return typing["decimal_type"]
    raise OutpatientSilverError(f"Measure has no governed type: {source_column}")


def normalized_measure_expression(source_column: str, contract: dict[str, Any]) -> str:
    """Create a typed expression while preserving source nulls."""
    source = quote_identifier(source_column)
    target = quote_identifier(target_column_name(source_column))
    target_type = measure_type(source_column, contract)
    return f"TRY_CAST(TRIM(CAST({source} AS VARCHAR)) AS {target_type}) AS {target}"


def normalized_dimension_expression(
    source_column: str, target_column: str, contract: dict[str, Any]
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
    source_column: str, target_column: str, contract: dict[str, Any]
) -> str:
    """Preserve whether a nullable dimension was absent in Bronze."""
    policy = contract["nullable_dimension_policy"].get(target_column)
    if not policy or not policy.get("preserve_missing_indicator"):
        raise OutpatientSilverError(
            f"Dimension has no governed missing indicator: {target_column}"
        )
    source = quote_identifier(source_column)
    target = quote_identifier(f"{target_column}_is_missing")
    return (
        f"CASE WHEN {source} IS NULL OR TRIM(CAST({source} AS VARCHAR)) = '' "
        f"THEN TRUE ELSE FALSE END AS {target}"
    )


def suppression_status_expression(group: str, contract: dict[str, Any]) -> str:
    """Derive an explicit CMS publication status without reconstruction."""
    if group == "provider_apc_summary":
        condition = '"comprehensive_apc_services" IS NULL'
    elif group == "beneficiary_count":
        condition = '"beneficiary_count" IS NULL'
    elif group == "outlier_detail":
        condition = '"outlier_services" IS NULL'
    else:
        raise OutpatientSilverError(f"Unknown suppression group: {group}")
    if group not in contract["suppression_semantics"]:
        raise OutpatientSilverError(f"Ungoverned suppression group: {group}")
    alias = quote_identifier(f"{group}_status")
    return f"CASE WHEN {condition} THEN 'suppressed' ELSE 'published' END AS {alias}"


def service_volume_band_expression(contract: dict[str, Any]) -> str:
    """Build the contract-driven service-volume band."""
    settings = contract["service_volume_bands"]
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
    suppressed = sql_literal(settings["value_when_suppressed"])
    return (
        f"CASE WHEN {measure} IS NULL THEN {suppressed} "
        + " ".join(clauses)
        + " ELSE NULL END AS service_volume_band"
    )
