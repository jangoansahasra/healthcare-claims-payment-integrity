from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "part_d_silver.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_contract_identifies_observed_part_d_benchmark() -> None:
    contract = load_contract()
    model = contract["model"]

    assert contract["contract_version"] == 1
    assert model["name"] == "cms_part_d_provider_summary_silver"
    assert model["source_id"] == "cms_part_d_provider_summary"
    assert model["source_layer"] == "bronze"
    assert model["target_layer"] == "silver"
    assert model["data_role"] == "observed_benchmark"


def test_business_key_preserves_prescriber_year_grain() -> None:
    contract = load_contract()

    assert contract["business_key"] == [
        "prescriber_npi",
        "reporting_year",
    ]
    assert "reporting year" in contract["model"]["grain"]


def test_governance_separates_benchmarks_from_audit_findings() -> None:
    governance = load_contract()["governance"]

    assert governance["source_authority"] == (
        "Centers for Medicare & Medicaid Services"
    )
    assert governance["official_data_dictionary"].startswith("https://data.cms.gov/")
    assert governance["contains_real_provider_identifiers"] is True
    assert governance["contains_beneficiary_identifiers"] is False
    assert "synthetic pharmacy claims calibration" in governance["permitted_uses"]
    assert (
        "attributing injected anomalies to real prescribers"
        in governance["prohibited_uses"]
    )
    assert (
        "representing total drug cost as insurer-only liability"
        in governance["prohibited_uses"]
    )


def test_source_schema_requires_canonical_aliases() -> None:
    schema = load_contract()["source_schema"]

    assert schema["expected_source_column_count"] == 84
    assert schema["canonical_identifier"] == "Prscrbr_NPI"
    assert schema["required_canonical_columns"] == [
        "Prscrbr_NPI",
        "Prscrbr_Type_src",
    ]
    assert schema["reject_unresolved_schema_aliases"] is True


def test_expected_source_dimensions_are_mapped() -> None:
    dimensions = load_contract()["source_dimensions"]

    assert len(dimensions) == 17
    assert dimensions["Prscrbr_NPI"] == "prescriber_npi"
    assert dimensions["Prscrbr_Type"] == "prescriber_type"
    assert dimensions["Prscrbr_Type_src"] == "prescriber_type_source"
    assert dimensions["Prscrbr_Cntry"] == "prescriber_country_code"
    assert len(set(dimensions.values())) == len(dimensions)


def test_historical_attributes_remain_year_specific() -> None:
    history = load_contract()["historical_attribute_handling"]

    assert history["prescriber_attributes_are_year_specific"] is True
    assert history["preserve_reported_values_by_year"] is True
    assert history["do_not_overwrite_history_with_latest_values"] is True
    assert "prescriber_type" in history["tracked_attributes"]
    assert "prescriber_type_source" in history["tracked_attributes"]
    assert "prescriber_country_code" in history["tracked_attributes"]


def test_nullable_dimensions_have_explicit_unknown_policy() -> None:
    policy = load_contract()["nullable_dimension_policy"]

    assert policy["prescriber_type"] == {
        "observed_null_or_blank_rows": 27,
        "silver_value_when_missing": "Unknown",
        "preserve_missing_indicator": True,
    }
    assert policy["prescriber_ruca_code"] == {
        "observed_null_or_blank_rows": 8977,
        "silver_value_when_missing": "Unknown",
        "preserve_missing_indicator": True,
    }
    assert policy["prescriber_country_code"]["nullable"] is False
    assert policy["prescriber_state_abbreviation"]["nullable"] is False


def test_numeric_measure_classes_are_complete_and_disjoint() -> None:
    typing = load_contract()["numeric_typing"]
    integers = set(typing["integer_columns"])
    decimal_groups = typing["decimal_measure_classes"]
    decimals = [column for columns in decimal_groups.values() for column in columns]

    assert len(integers) == 37
    assert len(decimals) == 19
    assert len(decimals) == len(set(decimals))
    assert integers.isdisjoint(decimals)
    assert len(integers | set(decimals)) == 56
    assert typing["integer_type"] == "BIGINT"
    assert typing["decimal_type"] == "DECIMAL(38, 6)"
    assert typing["use_try_cast"] is True


def test_suppression_groups_preserve_official_tokens() -> None:
    suppression = load_contract()["suppression"]
    indicators = suppression["indicators"]

    assert len(indicators) == 11
    assert suppression["statuses"] == {
        "*": "primary_suppressed",
        "#": "counter_suppressed",
    }
    assert "between 1 and 10" in (suppression["official_definitions"]["*"])
    assert suppression["prohibit_suppressed_value_reconstruction"] is True
    assert suppression["prohibit_zero_imputation"] is True

    assert indicators["GE65_Sprsn_Flag"]["affected_measures"] == [
        "GE65_Tot_Clms",
        "GE65_Tot_30day_Fills",
        "GE65_Tot_Drug_Cst",
        "GE65_Tot_Day_Suply",
    ]
    assert indicators["Antpsyct_GE65_Sprsn_Flag"]["allowed_tokens"] == ["*"]
    assert indicators["Antpsyct_GE65_Bene_Suprsn_Flag"]["allowed_tokens"] == ["*"]


def test_suppression_affected_measures_are_not_duplicated() -> None:
    indicators = load_contract()["suppression"]["indicators"]
    affected = [
        measure
        for settings in indicators.values()
        for measure in settings["affected_measures"]
    ]

    assert len(affected) == len(set(affected))


def test_unflagged_nulls_remain_unclassified() -> None:
    handling = load_contract()["unflagged_null_handling"]

    assert handling["preserve_all_source_nulls"] is True
    assert handling["do_not_impute_zero"] is True
    assert handling["create_metric_level_null_summary"] is True
    assert handling["source_blank_status"] == "source_blank_reason_unclassified"
    assert handling["do_not_infer_suppression_reason_without_flag"] is True


def test_standardized_fill_disclosure_is_preserved() -> None:
    disclosure = load_contract()["standardized_fill_disclosure"]

    assert disclosure["source_method"] == ("claim days supplied divided by 30")
    assert disclosure["source_event_bottom_code"] == 1
    assert disclosure["source_event_top_code"] == 12
    assert disclosure["aggregate_values_are_not_reverse_adjusted"] is True
    assert disclosure["disclose_in_kpi_dictionary"] is True


def test_prescriber_size_bands_are_contiguous() -> None:
    size = load_contract()["prescriber_size_bands"]
    bands = size["bands"]

    assert size["measure"] == "tot_clms"
    assert size["reference_minimum"] == 11
    assert bands[0] == {
        "name": "small",
        "minimum_inclusive": 11,
        "maximum_inclusive": 55,
    }
    assert bands[-1] == {
        "name": "very_large",
        "minimum_inclusive": 939,
        "maximum_inclusive": None,
    }

    for current, following in zip(
        bands,
        bands[1:],
        strict=False,
    ):
        assert current["maximum_inclusive"] + 1 == following["minimum_inclusive"]


def test_benchmark_cohorts_are_country_safe() -> None:
    contract = load_contract()
    cohorts = contract["benchmark_cohorts"]
    geography = contract["geographic_benchmarking"]

    assert "prescriber_country_code" in cohorts["dimensions"]
    assert "prescriber_type_source" in cohorts["dimensions"]
    assert cohorts["minimum_peer_group_size"] == 11
    assert cohorts["missing_prescriber_type_bucket"] == "Unknown"
    assert cohorts["missing_ruca_bucket"] == "Unknown"
    assert cohorts["prohibit_outlier_as_fraud_label"] is True
    assert geography["domestic_country_code"] == "US"
    assert geography["state_and_ruca_cohorts_domestic_only"] is True
    assert geography["prohibit_cross_country_peer_comparisons"] is True
    assert geography["retain_foreign_prescriber_rows"] is True


def test_public_reporting_excludes_direct_prescriber_details() -> None:
    reporting = load_contract()["privacy_and_reporting"]
    excluded = set(reporting["public_dashboard_excluded_fields"])

    assert reporting["minimum_public_peer_group_size"] == 11
    assert reporting["expose_real_prescriber_anomaly_flags"] is False
    assert reporting["label_real_prescriber_results_as_benchmarks"] is True
    assert reporting["prohibit_prescriber_fraud_labels"] is True
    assert {
        "prescriber_last_or_organization_name",
        "prescriber_first_name",
        "prescriber_middle_initial",
        "prescriber_credentials",
        "prescriber_street_address_1",
        "prescriber_street_address_2",
        "prescriber_zip5",
    }.issubset(excluded)


def test_output_paths_use_governed_directories() -> None:
    paths = load_contract()["paths"]

    assert paths["bronze_glob"].startswith("data/processed/")
    assert paths["silver_output"].startswith("data/interim/")
    assert paths["suppression_output"].startswith("data/interim/")
    assert paths["quality_report"].startswith("data/metadata/quality/")
    assert paths["silver_output"].endswith(".parquet")
    assert paths["suppression_output"].endswith(".parquet")
    assert paths["quality_report"].endswith(".json")


def test_allowed_values_cover_observed_source_domains() -> None:
    allowed = load_contract()["allowed_values"]

    assert allowed["reporting_years"] == list(range(2019, 2025))
    assert set(allowed["prescriber_entity_code"]) == {"I", "O"}
    assert allowed["prescriber_type_source"] == [
        "Claim-Specialty",
        "NPPES-Specialty",
        "NPPES-Taxonomy",
    ]


def test_all_quality_rules_are_enabled() -> None:
    rules = load_contract()["quality_rules"]

    assert len(rules) == 24
    assert all(value is True for value in rules.values())
    assert rules["require_canonical_source_schema"] is True
    assert rules["reject_unparseable_numeric_values"] is True
    assert rules["require_suppression_detail_consistency"] is True
    assert rules["require_suppression_count_reconciliation"] is True
    assert rules["require_nullable_dimension_policy"] is True
    assert rules["require_country_safe_peer_configuration"] is True
    assert rules["prohibit_real_prescriber_anomaly_attribution"] is True
