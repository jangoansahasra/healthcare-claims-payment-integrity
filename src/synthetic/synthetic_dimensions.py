from __future__ import annotations

import hashlib
import json
import re
from calendar import monthrange
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import yaml


class SyntheticDimensionError(RuntimeError):
    """Raised when synthetic dimension configuration or output is invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping."""
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    if not isinstance(content, dict):
        raise SyntheticDimensionError(f"{path} must contain a YAML mapping")
    return content


def deterministic_unit(seed: int, namespace: str, index: int) -> float:
    """Return a stable fraction in [0, 1) for an entity field."""
    digest = hashlib.sha256(f"{seed}:{namespace}:{index}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def deterministic_integer(
    seed: int,
    namespace: str,
    index: int,
    minimum: int,
    maximum: int,
) -> int:
    """Return a stable integer within an inclusive range."""
    if minimum > maximum:
        raise SyntheticDimensionError(
            f"Invalid integer range for {namespace}: {minimum}>{maximum}"
        )
    width = maximum - minimum + 1
    return minimum + int(deterministic_unit(seed, namespace, index) * width)


def weighted_choice(
    entries: list[dict[str, Any]],
    unit: float,
) -> dict[str, Any]:
    """Select a configured weighted entry using a stable fraction."""
    if not entries:
        raise SyntheticDimensionError("Weighted choice requires at least one entry")
    total = sum(float(entry["weight"]) for entry in entries)
    if abs(total - 1.0) > 1e-9:
        raise SyntheticDimensionError(f"Weights must sum to 1.0; observed {total}")

    cumulative = 0.0
    for entry in entries:
        cumulative += float(entry["weight"])
        if unit < cumulative:
            return entry
    return entries[-1]


def normalized_weights(
    entries: list[dict[str, Any]], weight_key: str
) -> list[dict[str, Any]]:
    """Return copied entries with the selected weights normalized to one."""
    total = sum(float(entry[weight_key]) for entry in entries)
    if total <= 0:
        raise SyntheticDimensionError(
            "Eligible weighted entries must have positive weight"
        )
    return [{**entry, "weight": float(entry[weight_key]) / total} for entry in entries]


def month_starts(start: date, end: date) -> list[date]:
    """Return first-of-month dates spanning the inclusive reporting window."""
    current = date(start.year, start.month, 1)
    final = date(end.year, end.month, 1)
    months = []
    while current <= final:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def month_end(month: date, reporting_end: date) -> date:
    """Return the final covered day for a reporting month."""
    final = date(month.year, month.month, monthrange(month.year, month.month)[1])
    return min(final, reporting_end)


def generate_dimension_rows(
    contract: dict[str, Any],
    configuration: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic clean dimensions, eligibility, and assignments."""
    dataset = contract["dataset"]
    generation = contract["generation"]
    seed = int(dataset["deterministic_seed"])
    start = date.fromisoformat(str(dataset["reporting_start_date"]))
    end = date.fromisoformat(str(dataset["reporting_end_date"]))
    policy_start = date.fromisoformat(str(dataset["policy_start_date"]))
    months = month_starts(start, end)

    plan_config = configuration["plans"]
    if len(plan_config) != generation["plans"]:
        raise SyntheticDimensionError("Configured plan count does not match contract")

    plans = [
        {
            "plan_id": plan["plan_id"],
            "plan_type": plan["plan_type"],
            "product_line": plan["product_line"],
            "effective_date": start,
            "termination_date": None,
        }
        for plan in plan_config
    ]

    geography = configuration["geography_distribution"]
    member_config = configuration["member_distribution"]
    members = []
    membership_months = []
    for number in range(1, generation["members"] + 1):
        state = weighted_choice(
            geography,
            deterministic_unit(seed, "member_state", number),
        )
        sex = weighted_choice(
            member_config["sex"],
            deterministic_unit(seed, "member_sex", number),
        )["value"]
        band = weighted_choice(
            member_config["birth_year_bands"],
            deterministic_unit(seed, "member_birth_band", number),
        )
        birth_year = deterministic_integer(
            seed,
            "member_birth_year",
            number,
            int(band["minimum"]),
            int(band["maximum"]),
        )
        member_id = f"MBR{number:08d}"
        members.append(
            {
                "member_id": member_id,
                "birth_year": birth_year,
                "sex_code": sex,
                "state_code": state["state_code"],
                "synthetic_record": True,
            }
        )

        age_at_start = start.year - birth_year
        eligible_plans = [
            item for item in plan_config if age_at_start >= int(item["minimum_age"])
        ]
        plan = weighted_choice(
            normalized_weights(eligible_plans, "member_weight"),
            deterministic_unit(seed, "member_plan", number),
        )
        start_offset = deterministic_integer(
            seed,
            "coverage_start",
            number,
            0,
            int(member_config["maximum_start_month_offset"]),
        )
        last_offset = len(months) - 1
        if deterministic_unit(seed, "coverage_termination", number) < float(
            member_config["early_termination_share"]
        ):
            earliest_end = min(
                last_offset,
                start_offset + int(member_config["minimum_coverage_months"]) - 1,
            )
            last_offset = deterministic_integer(
                seed,
                "coverage_end",
                number,
                earliest_end,
                last_offset,
            )

        for coverage_month in months[start_offset : last_offset + 1]:
            membership_months.append(
                {
                    "member_id": member_id,
                    "plan_id": plan["plan_id"],
                    "coverage_month": coverage_month,
                    "coverage_start_date": max(start, coverage_month),
                    "coverage_end_date": month_end(coverage_month, end),
                    "coverage_status": "active",
                }
            )

    provider_config = configuration["provider_distribution"]
    providers = []
    provider_regions: dict[str, str] = {}
    for number in range(1, generation["providers"] + 1):
        provider_id = f"PRV{number:06d}"
        state = weighted_choice(
            geography,
            deterministic_unit(seed, "provider_state", number),
        )
        entity = weighted_choice(
            provider_config["entity_type"],
            deterministic_unit(seed, "provider_entity", number),
        )
        specialty = weighted_choice(
            provider_config["specialties"],
            deterministic_unit(seed, "provider_specialty", number),
        )
        entity_type = specialty.get("required_entity_type", entity["value"])
        providers.append(
            {
                "provider_id": provider_id,
                "provider_entity_type": entity_type,
                "specialty_group": specialty["value"],
                "state_code": state["state_code"],
                "calibration_source_id": specialty["calibration_source_id"],
                "calibration_version": specialty["calibration_version"],
                "synthetic_record": True,
            }
        )
        provider_regions[provider_id] = state["region"]

    contract_config = configuration["provider_contracts"]
    if not contract_config["contract_every_provider_with_every_plan"]:
        raise SyntheticDimensionError("Only all-plan provider contracts are governed")
    provider_contracts = []
    contract_number = 0
    for provider in providers:
        for plan in plans:
            contract_number += 1
            method = weighted_choice(
                contract_config["reimbursement_methods"],
                deterministic_unit(seed, "reimbursement_method", contract_number),
            )
            provider_contracts.append(
                {
                    "contract_id": f"CON{contract_number:08d}",
                    "provider_id": provider["provider_id"],
                    "plan_id": plan["plan_id"],
                    "effective_date": start,
                    "termination_date": None,
                    "reimbursement_method": method["value"],
                }
            )

    policy = configuration["policy_assignment"]
    treated_regions = set(policy["treated_regions"])
    policy_assignments = []
    for number, provider in enumerate(providers, start=1):
        treated = provider_regions[provider["provider_id"]] in treated_regions
        policy_assignments.append(
            {
                "policy_assignment_id": f"POL{number:010d}",
                "provider_id": provider["provider_id"],
                "policy_id": policy["policy_id"],
                "treatment_group": (
                    policy["treatment_label"] if treated else policy["comparison_label"]
                ),
                "assignment_start_date": policy_start,
                "assignment_end_date": end,
            }
        )

    return {
        "member": members,
        "plan": plans,
        "provider": providers,
        "provider_contract": provider_contracts,
        "membership_month": membership_months,
        "policy_assignment": policy_assignments,
    }


def arrow_type(type_name: str) -> pa.DataType:
    """Map governed contract types to Arrow types."""
    mapping = {
        "BOOLEAN": pa.bool_(),
        "DATE": pa.date32(),
        "INTEGER": pa.int32(),
        "BIGINT": pa.int64(),
        "SMALLINT": pa.int16(),
        "TINYINT": pa.int8(),
        "TIMESTAMP": pa.timestamp("us"),
        "VARCHAR": pa.string(),
        "DECIMAL(18,2)": pa.decimal128(18, 2),
        "DECIMAL(18,4)": pa.decimal128(18, 4),
    }
    try:
        return mapping[type_name]
    except KeyError as error:
        raise SyntheticDimensionError(
            f"Unsupported contract type: {type_name}"
        ) from error


def table_schema(contract: dict[str, Any], table_name: str) -> pa.Schema:
    """Build an Arrow schema directly from the table contract."""
    try:
        columns = contract["tables"][table_name]["columns"]
    except KeyError as error:
        raise SyntheticDimensionError(
            f"Unknown contract table: {table_name}"
        ) from error
    return pa.schema(
        [
            pa.field(
                column_name,
                arrow_type(details["type"]),
                nullable=details["nullable"],
            )
            for column_name, details in columns.items()
        ]
    )


def content_hash(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """Hash canonical ordered row content independently of Parquet metadata."""
    digest = hashlib.sha256()
    for row in rows:
        values = []
        for value in (row[column] for column in columns):
            if isinstance(value, date):
                values.append(value.isoformat())
            elif isinstance(value, Decimal):
                values.append(format(value, "f"))
            else:
                values.append(value)
        digest.update(
            json.dumps(values, ensure_ascii=True, separators=(",", ":")).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def validate_generated_rows(
    rows_by_table: dict[str, list[dict[str, Any]]],
    contract: dict[str, Any],
) -> dict[str, bool]:
    """Evaluate contract, key, relationship, date, and privacy checks."""
    generation = contract["generation"]
    dataset = contract["dataset"]
    start = date.fromisoformat(str(dataset["reporting_start_date"]))
    end = date.fromisoformat(str(dataset["reporting_end_date"]))
    policy_start = date.fromisoformat(str(dataset["policy_start_date"]))
    tables = contract["tables"]

    checks: dict[str, bool] = {
        "member_row_count": len(rows_by_table["member"]) == generation["members"],
        "plan_row_count": len(rows_by_table["plan"]) == generation["plans"],
        "provider_row_count": len(rows_by_table["provider"]) == generation["providers"],
        "policy_cohorts_nonempty": {
            row["treatment_group"] for row in rows_by_table["policy_assignment"]
        }
        == {"treated", "comparison"},
        "members_are_synthetic": all(
            row["synthetic_record"] for row in rows_by_table["member"]
        ),
        "providers_are_synthetic": all(
            row["synthetic_record"] for row in rows_by_table["provider"]
        ),
        "facility_providers_are_organizations": all(
            row["provider_entity_type"] == "organization"
            for row in rows_by_table["provider"]
            if row["specialty_group"] in {"inpatient_facility", "outpatient_facility"}
        ),
        "coverage_dates_valid": all(
            start <= row["coverage_start_date"] <= row["coverage_end_date"] <= end
            for row in rows_by_table["membership_month"]
        ),
        "contract_dates_valid": all(
            row["effective_date"] <= (row["termination_date"] or end)
            for row in rows_by_table["provider_contract"]
        ),
        "policy_dates_valid": all(
            row["assignment_start_date"] == policy_start
            and row["assignment_end_date"] == end
            for row in rows_by_table["policy_assignment"]
        ),
    }

    for table_name, rows in rows_by_table.items():
        table_contract = tables[table_name]
        expected_columns = list(table_contract["columns"])
        checks[f"{table_name}_columns"] = all(
            list(row) == expected_columns for row in rows
        )
        primary_key = table_contract["primary_key"]
        keys = [tuple(row[column] for column in primary_key) for row in rows]
        checks[f"{table_name}_primary_key"] = len(keys) == len(set(keys)) and all(
            all(value is not None for value in key) for key in keys
        )

    for table_name, table_contract in tables.items():
        if table_name not in rows_by_table:
            continue
        for index, foreign_key in enumerate(table_contract.get("foreign_keys", [])):
            target_match = re.fullmatch(
                r"([a-z_]+)\(([a-z_, ]+)\)", foreign_key["references"]
            )
            if target_match is None:
                raise SyntheticDimensionError(
                    f"Invalid foreign-key reference: {foreign_key['references']}"
                )
            target_table = target_match.group(1)
            if target_table not in rows_by_table:
                continue
            source_columns = foreign_key["columns"]
            target_columns = [
                column.strip() for column in target_match.group(2).split(",")
            ]
            target_keys = {
                tuple(row[column] for column in target_columns)
                for row in rows_by_table[target_table]
            }
            checks[f"{table_name}_foreign_key_{index + 1}"] = all(
                any(row[column] is None for column in source_columns)
                or tuple(row[column] for column in source_columns) in target_keys
                for row in rows_by_table[table_name]
            )

    for identifier, pattern in contract["identifier_formats"].items():
        applicable = [
            rows
            for table_name, rows in rows_by_table.items()
            if identifier in tables[table_name]["columns"]
        ]
        if applicable:
            checks[f"{identifier}_format"] = all(
                re.fullmatch(pattern, row[identifier]) is not None
                for rows in applicable
                for row in rows
            )

    return checks
