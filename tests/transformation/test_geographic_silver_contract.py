from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "geographic_silver.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_identifies_expected_model_and_source() -> None:
    contract = load_contract()

    assert contract["contract_version"] == 1
    assert contract["model"]["name"] == "cms_geographic_variation_silver"
    assert contract["model"]["source_id"] == "cms_geographic_variation"
    assert contract["model"]["source_layer"] == "bronze"
    assert contract["model"]["target_layer"] == "silver"


def test_business_key_has_expected_order() -> None:
    contract = load_contract()

    assert contract["business_key"] == [
        "year",
        "geography_level",
        "geography_id",
        "beneficiary_age_level",
    ]


def test_required_source_dimensions_are_mapped() -> None:
    contract = load_contract()
    dimensions = contract["source_dimensions"]

    assert set(dimensions) == {
        "YEAR",
        "BENE_GEO_LVL",
        "BENE_GEO_DESC",
        "BENE_GEO_CD",
        "BENE_AGE_LVL",
    }
    assert dimensions["YEAR"]["type"] == "INTEGER"
    assert dimensions["BENE_GEO_CD"]["nullable"] is True
    assert all(item["target"] for item in dimensions.values())


def test_special_value_classes_are_disjoint() -> None:
    contract = load_contract()
    special_values = contract["special_values"]

    token_groups = [
        set(special_values["suppression_tokens"]),
        set(special_values["not_applicable_tokens"]),
        set(special_values["missing_tokens"]),
    ]

    assert all(token_groups)
    assert token_groups[0].isdisjoint(token_groups[1])
    assert token_groups[0].isdisjoint(token_groups[2])
    assert token_groups[1].isdisjoint(token_groups[2])
    assert special_values["suppressed_values_become_null"] is True
    assert special_values["not_applicable_values_become_null"] is True
    assert special_values["preserve_special_value_lineage"] is True


def test_geography_rules_cover_coded_and_aggregate_rows() -> None:
    contract = load_contract()
    rules = contract["geography_identifier_rules"]

    fixed_ids = {rule["geography_id"] for rule in rules if "geography_id" in rule}
    source_code_levels = {
        rule["geography_level"]
        for rule in rules
        if rule.get("use_source_geography_code")
    }

    assert fixed_ids == {"US", "AGG_TERRITORY", "AGG_ZZ"}
    assert source_code_levels == {"State", "County"}


def test_allowed_values_match_observed_source_domains() -> None:
    contract = load_contract()
    allowed_values = contract["allowed_values"]

    assert allowed_values["geography_level"] == [
        "National",
        "State",
        "County",
    ]
    assert allowed_values["beneficiary_age_level"] == [
        "All",
        "<65",
        ">=65",
    ]
    assert allowed_values["minimum_year"] == 2014
    assert allowed_values["maximum_year"] == 2024


def test_output_paths_use_governed_directories() -> None:
    contract = load_contract()
    paths = contract["paths"]

    assert paths["bronze_input"].startswith("data/processed/")
    assert paths["silver_output"].startswith("data/interim/")
    assert paths["value_status_output"].startswith("data/interim/")
    assert paths["quality_report"].startswith("data/metadata/quality/")
    assert paths["silver_output"].endswith(".parquet")
    assert paths["value_status_output"].endswith(".parquet")
    assert paths["quality_report"].endswith(".json")


def test_all_quality_rules_are_enabled() -> None:
    contract = load_contract()
    quality_rules = contract["quality_rules"]

    assert len(quality_rules) == 10
    assert all(value is True for value in quality_rules.values())
