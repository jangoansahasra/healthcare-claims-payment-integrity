from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONTRACT_PATH = Path("config/geographic_silver.yml")


class SilverTransformationError(RuntimeError):
    """Raised when bronze data cannot satisfy the silver contract."""


def load_contract(path: Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    """Load the governed geographic silver contract."""
    if not path.exists():
        raise SilverTransformationError(f"Silver contract does not exist: {path}")

    contract = yaml.safe_load(path.read_text(encoding="utf-8"))

    if not isinstance(contract, dict):
        raise SilverTransformationError("Silver contract must contain a mapping")

    return contract


def quote_identifier(identifier: str) -> str:
    """Safely quote a DuckDB identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def sql_literal(value: str) -> str:
    """Safely quote a DuckDB string literal."""
    return "'" + value.replace("'", "''") + "'"


def source_measure_columns(
    source_columns: list[str],
    contract: dict[str, Any],
) -> list[str]:
    """Return source columns governed as analytical measures."""
    excluded = set(contract["measure_typing"]["excluded_columns"])
    return [column for column in source_columns if column not in excluded]


def target_measure_name(source_column: str) -> str:
    """Return the normalized silver measure name."""
    return source_column.lower()


def measure_type(source_column: str, contract: dict[str, Any]) -> str:
    """Resolve the governed target type for a source measure."""
    typing = contract["measure_typing"]
    integer_suffixes = tuple(typing["integer_suffixes"])

    if source_column.endswith(integer_suffixes):
        return typing["integer_type"]

    return typing["decimal_type"]


def normalized_measure_expression(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Build a suppression-aware typed measure expression."""
    special_values = contract["special_values"]
    special_tokens = [
        *special_values["suppression_tokens"],
        *special_values["missing_tokens"],
        *special_values["not_applicable_tokens"],
    ]
    token_sql = ", ".join(sql_literal(token) for token in special_tokens)
    source_sql = quote_identifier(source_column)
    target_sql = quote_identifier(target_measure_name(source_column))
    target_type = measure_type(source_column, contract)

    return (
        f"CASE WHEN {source_sql} IS NULL "
        f"OR TRIM({source_sql}) IN ({token_sql}) "
        f"THEN NULL "
        f"ELSE TRY_CAST(TRIM({source_sql}) AS {target_type}) "
        f"END AS {target_sql}"
    )


def geography_identifier_expression(contract: dict[str, Any]) -> str:
    """Build the contract-driven normalized geography identifier."""
    fixed_clauses: list[str] = []
    coded_levels: list[str] = []

    for rule in contract["geography_identifier_rules"]:
        if rule.get("use_source_geography_code"):
            coded_levels.append(sql_literal(rule["geography_level"]))
            continue

        conditions = [
            f"BENE_GEO_LVL = {sql_literal(rule['geography_level'])}",
            f"BENE_GEO_DESC = {sql_literal(rule['geography_name'])}",
        ]

        if rule["source_geography_code"] is None:
            conditions.append("BENE_GEO_CD IS NULL")
        else:
            conditions.append(
                "BENE_GEO_CD = " + sql_literal(str(rule["source_geography_code"]))
            )

        fixed_clauses.append(
            "WHEN "
            + " AND ".join(conditions)
            + " THEN "
            + sql_literal(rule["geography_id"])
        )

    coded_level_sql = ", ".join(coded_levels)

    return (
        "CASE "
        + " ".join(fixed_clauses)
        + f" WHEN BENE_GEO_LVL IN ({coded_level_sql}) "
        + "AND BENE_GEO_CD IS NOT NULL "
        + "THEN UPPER(BENE_GEO_LVL) || ':' || BENE_GEO_CD "
        + "ELSE NULL END AS geography_id"
    )


def invalid_numeric_predicate(
    source_column: str,
    contract: dict[str, Any],
) -> str:
    """Identify non-special source values that cannot be typed."""
    special_values = contract["special_values"]
    special_tokens = [
        *special_values["suppression_tokens"],
        *special_values["missing_tokens"],
        *special_values["not_applicable_tokens"],
    ]
    token_sql = ", ".join(sql_literal(token) for token in special_tokens)
    source_sql = quote_identifier(source_column)
    target_type = measure_type(source_column, contract)

    return (
        f"{source_sql} IS NOT NULL "
        f"AND TRIM({source_sql}) NOT IN ({token_sql}) "
        f"AND TRY_CAST(TRIM({source_sql}) AS {target_type}) IS NULL"
    )
