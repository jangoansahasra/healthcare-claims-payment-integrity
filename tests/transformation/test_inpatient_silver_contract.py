from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "inpatient_silver.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_identifies_observed_inpatient_benchmark() -> None:
    contract = load_contract()
    model = contract["model"]

    assert contract["contract_version"] == 1
    assert model == {
        "name": "cms_inpatient_provider_service_silver",
        "source_id": "cms_inpatient_provider_service",
        "source_layer": "bronze",
        "target_layer": "silver",
        "data_role": "observed_benchmark",
        "grain": "one row per hospital CCN, MS-DRG, and reporting year",
    }


def test_business_key_preserves_hospital_drg_year_grain() -> None:
    assert load_contract()["business_key"] == [
        "hospital_ccn",
        "ms_drg_code",
        "reporting_year",
    ]


def test_governance_uses_official_cms_authority() -> None:
    governance = load_contract()["governance"]

    assert governance["source_authority"] == (
        "Centers for Medicare & Medicaid Services"
    )
    assert governance["official_dataset"].startswith("https://data.cms.gov/")
    assert governance["official_data_dictionary"].startswith("https://data.cms.gov/")
    assert governance["contains_real_provider_identifiers"] is True
    assert governance["contains_beneficiary_identifiers"] is False
    assert "synthetic inpatient claims calibration" in governance["permitted_uses"]
    assert (
        "presenting a benchmark outlier as fraud or incorrect payment"
        in governance["prohibited_uses"]
    )


def test_source_schema_and_dimensions_are_complete() -> None:
    contract = load_contract()
    schema = contract["source_schema"]
    dimensions = contract["source_dimensions"]

    assert schema["expected_cms_column_count"] == 15
    assert schema["expected_lineage_column_count"] == 4
    assert len(dimensions) == 11
    assert dimensions["Rndrng_Prvdr_CCN"] == "hospital_ccn"
    assert dimensions["Rndrng_Prvdr_St"] == "hospital_street_address"
    assert dimensions["Rndrng_Prvdr_State_FIPS"] == "hospital_state_fips"
    assert dimensions["DRG_Cd"] == "ms_drg_code"
    assert len(set(dimensions.values())) == len(dimensions)


def test_hospital_attributes_remain_year_specific() -> None:
    history = load_contract()["historical_attribute_handling"]

    assert history["hospital_attributes_are_year_specific"] is True
    assert history["preserve_reported_values_by_year"] is True
    assert history["do_not_overwrite_history_with_latest_values"] is True
    assert history["observed_hospitals_with_changes"] == {
        "hospital_name": 580,
        "hospital_city": 23,
        "hospital_street_address": 157,
        "hospital_state_fips": 0,
        "hospital_zip5": 68,
        "hospital_ruca_code": 119,
    }


def test_drg_descriptions_remain_year_specific() -> None:
    policy = load_contract()["drg_description_handling"]

    assert policy["descriptions_are_year_specific"] is True
    assert policy["preserve_reported_description_by_year"] is True
    assert policy["do_not_overwrite_history_with_latest_description"] is True
    assert policy["observed_codes_with_description_changes"] == 11


def test_nullable_ruca_has_explicit_unknown_policy() -> None:
    policy = load_contract()["nullable_dimension_policy"]

    assert policy["hospital_ruca_code"] == {
        "observed_null_or_blank_rows": 681,
        "silver_value_when_missing": "Unknown",
        "preserve_missing_indicator": True,
    }
    assert policy["hospital_ruca_description"] == {
        "observed_null_or_blank_rows": 681,
        "silver_value_when_missing": "Unknown",
        "preserve_missing_indicator": True,
    }
    assert policy["hospital_state_fips"]["nullable"] is False
    assert policy["hospital_zip5"]["nullable"] is False


def test_numeric_types_are_explicit_and_disjoint() -> None:
    typing = load_contract()["numeric_typing"]

    assert typing["integer_columns"] == ["Tot_Dschrgs"]
    assert typing["decimal_columns"] == [
        "Avg_Submtd_Cvrd_Chrg",
        "Avg_Tot_Pymt_Amt",
        "Avg_Mdcr_Pymt_Amt",
    ]
    assert set(typing["integer_columns"]).isdisjoint(typing["decimal_columns"])
    assert typing["integer_type"] == "BIGINT"
    assert typing["decimal_type"] == "DECIMAL(38, 6)"
    assert typing["use_try_cast"] is True


def test_publication_threshold_is_not_treated_as_zero() -> None:
    threshold = load_contract()["publication_threshold"]

    assert threshold["measure"] == "total_discharges"
    assert threshold["minimum_published_value"] == 11
    assert "10 or fewer" in threshold["cms_rule"]
    assert threshold["absence_is_not_zero"] is True
    assert threshold["prohibit_reconstruction"] is True


def test_payment_semantics_distinguish_charge_total_and_medicare() -> None:
    payment = load_contract()["payment_semantics"]

    assert payment["average_covered_charge"]["source_column"] == (
        "Avg_Submtd_Cvrd_Chrg"
    )
    assert payment["average_total_payment"]["source_column"] == ("Avg_Tot_Pymt_Amt")
    assert payment["average_medicare_payment"]["source_column"] == ("Avg_Mdcr_Pymt_Amt")
    assert payment["require_medicare_payment_not_above_total_payment"] is True
    assert payment["do_not_require_total_payment_below_covered_charge"] is True
    assert payment["preserve_total_payment_above_covered_charge"] is True
    assert payment["create_total_payment_above_covered_charge_indicator"] is True
    assert payment["observed_total_payment_above_covered_charge_rows"] == 1915


def test_identifier_patterns_and_years_are_governed() -> None:
    allowed = load_contract()["allowed_values"]

    assert allowed["reporting_years"] == list(range(2019, 2025))
    assert allowed["ccn_pattern"] == "^[0-9A-Za-z]{6}$"
    assert allowed["ms_drg_pattern"] == "^[0-9]{3}$"
    assert allowed["state_fips_pattern"] == "^[0-9]{2}$"
    assert allowed["zip5_pattern"] == "^[0-9]{5}$"


def test_discharge_volume_bands_are_contiguous() -> None:
    settings = load_contract()["discharge_volume_bands"]
    bands = settings["bands"]

    assert settings["measure"] == "total_discharges"
    assert bands[0] == {
        "name": "low",
        "minimum_inclusive": 11,
        "maximum_inclusive": 13,
    }
    assert bands[-1] == {
        "name": "very_high",
        "minimum_inclusive": 36,
        "maximum_inclusive": None,
    }

    for current, following in zip(bands, bands[1:], strict=False):
        assert current["maximum_inclusive"] + 1 == following["minimum_inclusive"]


def test_benchmark_cohorts_are_governed() -> None:
    cohorts = load_contract()["benchmark_cohorts"]

    assert cohorts["dimensions"] == [
        "ms_drg_code",
        "hospital_state_fips",
        "hospital_ruca_code",
        "discharge_volume_band",
        "reporting_year",
    ]
    assert cohorts["minimum_peer_group_size"] == 11
    assert cohorts["prohibit_outlier_as_fraud_label"] is True


def test_public_reporting_excludes_direct_hospital_details() -> None:
    reporting = load_contract()["privacy_and_reporting"]

    assert reporting["minimum_public_peer_group_size"] == 11
    assert reporting["expose_real_hospital_anomaly_flags"] is False
    assert reporting["label_real_hospital_results_as_benchmarks"] is True
    assert reporting["prohibit_hospital_fraud_labels"] is True
    assert set(reporting["public_dashboard_excluded_fields"]) == {
        "hospital_name",
        "hospital_street_address",
        "hospital_zip5",
    }


def test_quality_rules_cover_all_contract_invariants() -> None:
    rules = load_contract()["quality_rules"]

    assert len(rules) == 21
    assert all(rules.values())
    assert rules["preserve_source_row_count"] is True
    assert rules["require_medicare_payment_not_above_total_payment"] is True
    assert rules["report_total_payment_above_covered_charge"] is True
    assert rules["require_year_specific_hospital_attributes"] is True
    assert rules["require_year_specific_drg_descriptions"] is True
    assert rules["prohibit_real_hospital_anomaly_attribution"] is True
