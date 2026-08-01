from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PATH = PROJECT_ROOT / "config" / "physician_service_silver.yml"


def contract() -> dict:
    return yaml.safe_load(PATH.read_text(encoding="utf-8"))


def test_model_and_grain_are_governed() -> None:
    model = contract()["model"]
    assert model["name"] == "cms_physician_provider_service_silver"
    assert model["data_role"] == "observed_benchmark"
    assert contract()["business_key"] == [
        "rendering_npi",
        "hcpcs_code",
        "place_of_service_category",
        "reporting_year",
    ]


def test_numeric_types_preserve_fractional_services() -> None:
    typing = contract()["numeric_typing"]
    assert typing["integer_columns"] == ["Tot_Benes", "Tot_Bene_Day_Srvcs"]
    assert "Tot_Srvcs" in typing["decimal_columns"]
    assert typing["observed_fractional_service_rows"] == 55901
    assert typing["observed_hcpcs_with_fractional_services"] == 442


def test_payment_semantics_are_not_conflated() -> None:
    payment = contract()["payment_semantics"]
    assert payment["require_medicare_payment_not_above_allowed_amount"] is True
    assert (
        payment["average_standardized_medicare_payment"]["is_payment_component"]
        is False
    )
    assert payment["do_not_require_standardized_payment_below_allowed_amount"] is True
    assert payment["observed_standardized_above_allowed_rows"] == 3258449


def test_country_safe_peer_configuration() -> None:
    cohorts = contract()["benchmark_cohorts"]
    assert cohorts["require_country_safe_geography"] is True
    assert cohorts["use_state_and_ruca_only_for_us_providers"] is True
    assert cohorts["minimum_peer_group_size"] == 11


def test_historical_attributes_and_descriptions_are_preserved() -> None:
    history = contract()["historical_attribute_handling"]
    assert history["observed_providers_with_changes"]["provider_zip5"] == 222742
    descriptions = contract()["hcpcs_description_handling"]
    assert descriptions["observed_codes_with_description_changes"] == 4371
    assert descriptions["consumer_friendly_descriptions_not_for_clinical_coding"]


def test_quality_rules_are_complete() -> None:
    rules = contract()["quality_rules"]
    assert len(rules) == 24
    assert all(rules.values())
