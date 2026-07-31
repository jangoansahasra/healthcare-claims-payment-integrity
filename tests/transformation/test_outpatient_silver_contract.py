from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "outpatient_silver.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_identifies_observed_outpatient_benchmark() -> None:
    model = load_contract()["model"]
    assert model["name"] == "cms_outpatient_provider_service_silver"
    assert model["source_id"] == "cms_outpatient_provider_service"
    assert model["data_role"] == "observed_benchmark"
    assert "published reporting period" in model["grain"]


def test_business_key_preserves_hospital_apc_period_grain() -> None:
    assert load_contract()["business_key"] == [
        "hospital_ccn",
        "comprehensive_apc_code",
        "reporting_period",
    ]


def test_only_published_periods_are_governed() -> None:
    policy = load_contract()["available_period_policy"]
    assert policy["published_periods"] == [2019, 2021, 2023]
    assert policy["unavailable_periods"] == [2020, 2022, 2024]
    assert policy["interpolate_unavailable_periods"] is False
    assert policy["treat_unavailable_periods_as_zero"] is False


def test_source_schema_and_numeric_types_are_complete() -> None:
    contract = load_contract()
    assert contract["source_schema"]["expected_cms_column_count"] == 18
    assert len(contract["source_dimensions"]) == 11
    typing = contract["numeric_typing"]
    assert typing["integer_columns"] == ["Bene_Cnt", "CAPC_Srvcs", "Outlier_Srvcs"]
    assert len(typing["decimal_columns"]) == 4
    assert typing["preserve_nulls"] is True
    assert typing["prohibit_zero_imputation"] is True


def test_suppression_groups_match_cms_rules() -> None:
    suppression = load_contract()["suppression_semantics"]
    assert suppression["publication_minimum"] == 11
    assert suppression["provider_apc_summary"]["observed_suppressed_rows"] == 157739
    assert (
        suppression["beneficiary_count"]["observed_additional_suppressed_rows"] == 3350
    )
    assert suppression["outlier_detail"]["observed_suppressed_rows"] == 211218
    assert suppression["absence_is_not_zero"] is True
    assert suppression["prohibit_reconstruction"] is True


def test_payment_semantics_use_allowed_amount_as_ceiling() -> None:
    payment = load_contract()["payment_semantics"]
    assert payment["require_medicare_payment_not_above_allowed_amount"] is True
    assert payment["observed_allowed_above_submitted_charge_rows"] == 85
    assert payment["observed_payment_above_submitted_charge_rows"] == 49
    assert payment["observed_outlier_above_regular_payment_rows"] == 3082
    assert payment["do_not_require_allowed_amount_below_submitted_charge"] is True
    assert payment["do_not_require_outlier_amount_below_regular_payment"] is True


def test_historical_attributes_remain_period_specific() -> None:
    history = load_contract()["historical_attribute_handling"]
    assert history["observed_hospitals_with_changes"] == {
        "hospital_name": 518,
        "hospital_state_abbreviation": 0,
        "hospital_zip5": 60,
        "hospital_ruca_code": 124,
    }
    assert history["do_not_overwrite_history_with_latest_values"] is True


def test_nullable_ruca_has_explicit_policy() -> None:
    policy = load_contract()["nullable_dimension_policy"]
    assert policy["hospital_ruca_code"]["observed_null_or_blank_rows"] == 18
    assert policy["hospital_ruca_description"]["observed_null_or_blank_rows"] == 18
    assert policy["hospital_ruca_code"]["preserve_missing_indicator"] is True


def test_service_volume_bands_are_contiguous() -> None:
    settings = load_contract()["service_volume_bands"]
    bands = settings["bands"]
    assert settings["value_when_suppressed"] == "suppressed"
    for current, following in zip(bands, bands[1:], strict=False):
        assert current["maximum_inclusive"] + 1 == following["minimum_inclusive"]


def test_quality_rules_cover_governed_invariants() -> None:
    rules = load_contract()["quality_rules"]
    assert len(rules) == 26
    assert all(rules.values())
    assert rules["require_suppression_pattern_reconciliation"] is True
    assert rules["require_medicare_payment_not_above_allowed_amount"] is True
    assert rules["prohibit_unavailable_period_interpolation"] is True
    assert rules["prohibit_real_hospital_anomaly_attribution"] is True
