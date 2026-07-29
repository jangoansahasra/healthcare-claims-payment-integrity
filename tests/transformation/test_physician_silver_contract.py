from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "physician_silver.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_identifies_observed_benchmark_model() -> None:
    contract = load_contract()
    model = contract["model"]

    assert contract["contract_version"] == 1
    assert model["name"] == "cms_physician_provider_summary_silver"
    assert model["source_id"] == "cms_physician_provider_summary"
    assert model["source_layer"] == "bronze"
    assert model["target_layer"] == "silver"
    assert model["data_role"] == "observed_benchmark"


def test_business_key_preserves_provider_year_grain() -> None:
    contract = load_contract()

    assert contract["business_key"] == [
        "provider_npi",
        "reporting_year",
    ]
    assert "reporting year" in contract["model"]["grain"]


def test_governance_separates_benchmarks_from_audit_findings() -> None:
    contract = load_contract()
    governance = contract["governance"]

    assert governance["source_authority"] == (
        "Centers for Medicare & Medicaid Services"
    )
    assert governance["official_data_dictionary"].startswith("https://data.cms.gov/")
    assert governance["contains_real_provider_identifiers"] is True
    assert governance["contains_beneficiary_identifiers"] is False
    assert "synthetic claims calibration" in governance["permitted_uses"]
    assert (
        "attributing injected anomalies to real providers"
        in governance["prohibited_uses"]
    )
    assert (
        "presenting a benchmark outlier as fraud or incorrect payment"
        in governance["prohibited_uses"]
    )


def test_expected_source_dimensions_are_mapped() -> None:
    contract = load_contract()
    dimensions = contract["source_dimensions"]

    assert len(dimensions) == 17
    assert dimensions["Rndrng_NPI"] == "provider_npi"
    assert dimensions["Rndrng_Prvdr_Type"] == "provider_specialty"
    assert dimensions["Rndrng_Prvdr_State_Abrvtn"] == "provider_state_abbreviation"
    assert (
        dimensions["Rndrng_Prvdr_Mdcr_Prtcptg_Ind"]
        == "medicare_participation_indicator"
    )
    assert len(set(dimensions.values())) == len(dimensions)


def test_provider_attributes_remain_historical_by_year() -> None:
    contract = load_contract()
    history = contract["historical_attribute_handling"]

    assert history["provider_attributes_are_year_specific"] is True
    assert history["preserve_reported_values_by_year"] is True
    assert history["do_not_overwrite_history_with_latest_values"] is True
    assert "provider_specialty" in history["tracked_attributes"]
    assert "provider_state_abbreviation" in history["tracked_attributes"]
    assert "medicare_participation_indicator" in history["tracked_attributes"]


def test_numeric_typing_has_disjoint_column_classes() -> None:
    contract = load_contract()
    typing = contract["numeric_typing"]

    integer_columns = set(typing["integer_columns"])
    excluded_columns = set(typing["excluded_columns"])

    assert typing["integer_type"] == "BIGINT"
    assert typing["decimal_type"] == "DECIMAL(38, 6)"
    assert typing["use_try_cast"] is True
    assert len(integer_columns) == 20
    assert integer_columns.isdisjoint(excluded_columns)
    assert "Tot_Benes" in integer_columns
    assert "Rndrng_NPI" in excluded_columns
    assert "Drug_Sprsn_Ind" in excluded_columns
    assert "Med_Sprsn_Ind" in excluded_columns


def test_suppression_contract_preserves_official_meaning() -> None:
    contract = load_contract()
    suppression = contract["suppression"]

    assert set(suppression["official_definitions"]) == {"*", "#"}
    assert "fewer than 11" in suppression["official_definitions"]["*"]
    assert "counter-suppressed" in suppression["official_definitions"]["#"]
    assert suppression["statuses"] == {
        "*": "primary_suppressed_fewer_than_11",
        "#": "counter_suppressed",
    }
    assert set(suppression["indicators"]) == {
        "Drug_Sprsn_Ind",
        "Med_Sprsn_Ind",
    }
    assert suppression["suppressed_numeric_values_remain_null"] is True
    assert suppression["preserve_indicator_lineage"] is True
    assert suppression["prohibit_suppressed_value_reconstruction"] is True
    assert suppression["prohibit_zero_imputation"] is True


def test_top_coding_is_not_treated_as_exact_percentage() -> None:
    contract = load_contract()
    top_coding = contract["top_coding"]

    assert top_coding["create_row_level_top_coded_metric_count"] is True
    assert top_coding["expected_percentage_metric_count"] == 25
    assert top_coding["chronic_condition_percentage_suffix"] == "_Pct"
    assert top_coding["upper_bound"] == 75
    assert top_coding["value_at_upper_bound_means"] == (
        "seventy_five_percent_or_greater"
    )
    assert top_coding["preserve_numeric_value"] is True
    assert top_coding["create_top_coded_indicator"] is True
    assert top_coding["do_not_treat_as_exact_percentage"] is True


def test_benchmark_cohorts_are_peer_adjusted() -> None:
    contract = load_contract()
    cohorts = contract["benchmark_cohorts"]

    assert cohorts["dimensions"] == [
        "provider_specialty",
        "provider_country_code",
        "provider_state_abbreviation",
        "provider_ruca_code",
        "provider_entity_code",
        "reporting_year",
    ]
    assert cohorts["provider_size_measure"] == "tot_benes"
    assert cohorts["minimum_peer_group_size"] == 11
    assert cohorts["provider_size_bands"][-1]["maximum_inclusive"] is None
    assert "median" in cohorts["comparison_statistics"]
    assert "percentile_95" in cohorts["comparison_statistics"]
    assert cohorts["prohibit_outlier_as_fraud_label"] is True


def test_public_reporting_excludes_direct_provider_details() -> None:
    contract = load_contract()
    reporting = contract["privacy_and_reporting"]
    excluded = set(reporting["public_dashboard_excluded_fields"])

    assert reporting["minimum_public_peer_group_size"] == 11
    assert reporting["expose_real_provider_anomaly_flags"] is False
    assert reporting["label_real_provider_results_as_benchmarks"] is True
    assert reporting["prohibit_provider_fraud_labels"] is True
    assert {
        "provider_last_or_organization_name",
        "provider_first_name",
        "provider_middle_initial",
        "provider_credentials",
        "provider_street_address_1",
        "provider_street_address_2",
        "provider_zip5",
    }.issubset(excluded)


def test_output_paths_use_governed_directories() -> None:
    contract = load_contract()
    paths = contract["paths"]

    assert paths["bronze_glob"].startswith("data/processed/")
    assert paths["silver_output"].startswith("data/interim/")
    assert paths["suppression_output"].startswith("data/interim/")
    assert paths["quality_report"].startswith("data/metadata/quality/")
    assert paths["silver_output"].endswith(".parquet")
    assert paths["suppression_output"].endswith(".parquet")
    assert paths["quality_report"].endswith(".json")


def test_geographic_peers_do_not_mix_countries() -> None:
    contract = load_contract()
    geography = contract["geographic_benchmarking"]

    assert geography["domestic_country_code"] == "US"
    assert geography["require_country_in_peer_definition"] is True
    assert geography["state_and_ruca_cohorts_domestic_only"] is True
    assert geography["foreign_provider_cohort_dimension"] == "provider_country_code"
    assert geography["prohibit_cross_country_peer_comparisons"] is True
    assert geography["retain_foreign_provider_rows"] is True


def test_allowed_values_cover_complete_source_period() -> None:
    contract = load_contract()
    allowed = contract["allowed_values"]

    assert allowed["reporting_years"] == list(range(2019, 2025))
    assert set(allowed["provider_entity_code"]) == {"I", "O"}
    assert set(allowed["medicare_participation_indicator"]) == {"Y", "N"}


def test_all_quality_rules_are_enabled() -> None:
    contract = load_contract()
    quality_rules = contract["quality_rules"]

    assert len(quality_rules) == 23
    assert all(value is True for value in quality_rules.values())
    assert quality_rules["require_unique_business_key"] is True
    assert quality_rules["require_suppression_detail_consistency"] is True
    assert quality_rules["require_top_coded_percentage_indicator"] is True
    assert quality_rules["require_peer_group_threshold_configuration"] is True
    assert quality_rules["prohibit_real_provider_anomaly_attribution"] is True
    assert quality_rules["require_non_null_country_code"] is True
    assert quality_rules["require_country_safe_peer_configuration"] is True
    assert quality_rules["require_top_coding_count_reconciliation"] is True
