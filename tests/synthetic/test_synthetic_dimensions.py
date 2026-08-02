from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from src.synthetic.synthetic_dimensions import (
    SyntheticDimensionError,
    content_hash,
    deterministic_integer,
    deterministic_unit,
    generate_dimension_rows,
    load_yaml,
    month_starts,
    normalized_weights,
    table_schema,
    validate_generated_rows,
    weighted_choice,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "synthetic_data_contract.yml"
GENERATION_CONFIG_PATH = PROJECT_ROOT / "config" / "synthetic_dimension_generation.yml"
PROJECT_CONFIG_PATH = PROJECT_ROOT / "config" / "project.yml"
SOURCE_MANIFEST_PATH = PROJECT_ROOT / "config" / "source_manifest.yml"


def reduced_configuration() -> tuple[dict, dict]:
    contract = deepcopy(load_yaml(CONTRACT_PATH))
    configuration = deepcopy(load_yaml(GENERATION_CONFIG_PATH))
    contract["generation"]["members"] = 40
    contract["generation"]["providers"] = 12
    return contract, configuration


def test_deterministic_primitives_are_stable_and_bounded() -> None:
    first = deterministic_unit(20260724, "member_state", 1)

    assert first == deterministic_unit(20260724, "member_state", 1)
    assert first != deterministic_unit(20260724, "member_state", 2)
    assert 0 <= first < 1
    assert 4 <= deterministic_integer(20260724, "range", 1, 4, 9) <= 9


def test_invalid_integer_range_is_rejected() -> None:
    with pytest.raises(SyntheticDimensionError, match="Invalid integer range"):
        deterministic_integer(1, "invalid", 1, 5, 4)


def test_weighted_choice_requires_governed_weights() -> None:
    entries = [
        {"value": "A", "weight": 0.25},
        {"value": "B", "weight": 0.75},
    ]

    assert weighted_choice(entries, 0.1)["value"] == "A"
    assert weighted_choice(entries, 0.9)["value"] == "B"
    with pytest.raises(SyntheticDimensionError, match="sum to 1.0"):
        weighted_choice([{"value": "A", "weight": 0.5}], 0.1)


def test_weights_can_be_normalized_after_eligibility_filtering() -> None:
    entries = [
        {"value": "A", "member_weight": 0.35},
        {"value": "B", "member_weight": 0.15},
    ]
    normalized = normalized_weights(entries, "member_weight")

    assert sum(entry["weight"] for entry in normalized) == pytest.approx(1.0)
    assert weighted_choice(normalized, 0.8)["value"] == "B"


def test_month_starts_span_the_reporting_window() -> None:
    months = month_starts(date(2025, 1, 1), date(2026, 6, 30))

    assert len(months) == 18
    assert months[0] == date(2025, 1, 1)
    assert months[-1] == date(2026, 6, 1)


def test_generated_dimensions_have_expected_counts_and_relationships() -> None:
    contract, configuration = reduced_configuration()
    rows = generate_dimension_rows(contract, configuration)

    assert len(rows["member"]) == 40
    assert len(rows["plan"]) == 4
    assert len(rows["provider"]) == 12
    assert len(rows["provider_contract"]) == 48
    assert len(rows["policy_assignment"]) == 12
    assert 40 * 6 <= len(rows["membership_month"]) <= 40 * 18
    assert all(validate_generated_rows(rows, contract).values())
    assert all(
        provider["provider_entity_type"] == "organization"
        for provider in rows["provider"]
        if provider["specialty_group"] in {"inpatient_facility", "outpatient_facility"}
    )

    members = {row["member_id"]: row for row in rows["member"]}
    assert all(
        members[row["member_id"]]["birth_year"] <= 1960
        for row in rows["membership_month"]
        if row["plan_id"] == "PLN0003"
    )


def test_generation_is_content_stable_for_a_fixed_seed() -> None:
    contract, configuration = reduced_configuration()
    first = generate_dimension_rows(contract, configuration)
    second = generate_dimension_rows(contract, configuration)

    for table_name, first_rows in first.items():
        columns = list(contract["tables"][table_name]["columns"])
        assert content_hash(first_rows, columns) == content_hash(
            second[table_name], columns
        )


def test_contract_arrow_schemas_preserve_string_identifiers() -> None:
    contract = load_yaml(CONTRACT_PATH)

    member = table_schema(contract, "member")
    provider = table_schema(contract, "provider")
    eligibility = table_schema(contract, "membership_month")

    assert str(member.field("member_id").type) == "string"
    assert str(provider.field("provider_id").type) == "string"
    assert str(eligibility.field("coverage_month").type) == "date32[day]"


def test_plan_count_mismatch_is_rejected() -> None:
    contract, configuration = reduced_configuration()
    contract["generation"]["plans"] = 5

    with pytest.raises(SyntheticDimensionError, match="plan count"):
        generate_dimension_rows(contract, configuration)


def test_generation_distributions_and_calibration_sources_are_governed() -> None:
    configuration = load_yaml(GENERATION_CONFIG_PATH)
    project = load_yaml(PROJECT_CONFIG_PATH)
    manifest = load_yaml(SOURCE_MANIFEST_PATH)
    source_ids = {source["source_id"] for source in manifest["sources"]}

    weighted_groups = [
        configuration["member_distribution"]["sex"],
        configuration["member_distribution"]["birth_year_bands"],
        configuration["geography_distribution"],
        configuration["provider_distribution"]["entity_type"],
        configuration["provider_distribution"]["specialties"],
        configuration["provider_contracts"]["reimbursement_methods"],
    ]
    for entries in weighted_groups:
        assert sum(float(entry["weight"]) for entry in entries) == pytest.approx(1.0)

    assert sum(float(plan["member_weight"]) for plan in configuration["plans"]) == (
        pytest.approx(1.0)
    )
    assert (
        configuration["policy_assignment"]["treated_regions"]
        == project["generation"]["treated_regions"]
    )
    assert {
        specialty["calibration_source_id"]
        for specialty in configuration["provider_distribution"]["specialties"]
    } <= source_ids
