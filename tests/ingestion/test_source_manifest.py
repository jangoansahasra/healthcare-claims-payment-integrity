from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "config" / "source_manifest.yml"


def load_manifest() -> dict:
    """Load and validate the source manifest root structure."""
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = yaml.safe_load(file)

    assert isinstance(manifest, dict)
    return manifest


def test_source_manifest_has_required_sections() -> None:
    manifest = load_manifest()

    assert {
        "manifest_version",
        "last_reviewed",
        "project_data_policy",
        "sources",
        "excluded_from_core_analysis",
    } <= manifest.keys()


def test_source_ids_are_unique() -> None:
    sources = load_manifest()["sources"]
    source_ids = [source["source_id"] for source in sources]

    assert len(source_ids) == len(set(source_ids))


def test_sources_have_required_metadata() -> None:
    required_fields = {
        "source_id",
        "name",
        "publisher",
        "role",
        "domain",
        "grain",
        "source_page",
        "download_method",
        "requested_years",
        "latest_verified_year",
        "local_directory",
        "ingestion_status",
        "contains_real_healthcare_activity",
        "contains_direct_beneficiary_identifiers",
        "commit_raw_file",
    }

    for source in load_manifest()["sources"]:
        assert required_fields <= source.keys(), source["source_id"]


def test_requested_years_are_sorted_unique_and_include_latest() -> None:
    for source in load_manifest()["sources"]:
        requested_years = source["requested_years"]

        assert requested_years == sorted(set(requested_years))
        assert source["latest_verified_year"] == max(requested_years)


def test_observed_sources_meet_freshness_policy() -> None:
    manifest = load_manifest()
    review_year = date.fromisoformat(str(manifest["last_reviewed"])).year
    maximum_lag = manifest["project_data_policy"]["maximum_source_lag_years"]

    for source in manifest["sources"]:
        if source["role"] == "observed":
            source_lag = review_year - source["latest_verified_year"]
            assert source_lag <= maximum_lag, source["source_id"]


def test_source_urls_are_secure_and_official() -> None:
    approved_hosts = {"data.cms.gov", "www.cms.gov", "www.cdc.gov"}

    for source in load_manifest()["sources"]:
        urls = [source["source_page"]]
        if "api_docs" in source:
            urls.append(source["api_docs"])

        for url in urls:
            parsed = urlparse(url)
            assert parsed.scheme == "https"
            assert parsed.hostname in approved_hosts


def test_publication_and_privacy_controls_are_enforced() -> None:
    manifest = load_manifest()
    policy = manifest["project_data_policy"]

    assert policy["allow_restricted_data"] is False
    assert policy["allow_identifiable_beneficiary_data"] is False
    assert policy["allow_proprietary_cpt_descriptions"] is False
    assert policy["commit_complete_raw_files"] is False
    assert policy["commit_complete_processed_files"] is False
    assert policy["require_sha256_checksum"] is True

    for source in manifest["sources"]:
        assert source["contains_direct_beneficiary_identifiers"] is False
        assert source["commit_raw_file"] is False


def test_legacy_bsa_data_is_excluded_from_core_analysis() -> None:
    excluded_sources = load_manifest()["excluded_from_core_analysis"]

    assert any(
        "Basic Stand Alone" in source["source"]
        and source["permitted_use"] == "Optional legacy-ingestion appendix only."
        for source in excluded_sources
    )


def test_cms_catalog_sources_have_catalog_titles() -> None:
    for source in load_manifest()["sources"]:
        if source["download_method"] == "cms_data_api_catalog":
            assert source.get("catalog_title")


def test_ingestion_status_values_are_governed() -> None:
    allowed_statuses = {
        "planned",
        "bronze_complete",
        "silver_complete",
    }

    for source in load_manifest()["sources"]:
        assert source["ingestion_status"] in allowed_statuses


def test_part_d_provider_schema_drift_is_documented() -> None:
    sources = {source["source_id"]: source for source in load_manifest()["sources"]}
    part_d = sources["cms_part_d_provider_summary"]
    normalization = part_d["schema_normalization"]

    assert part_d["local_directory"] == ("data/raw/cms/cms_part_d_provider_summary")
    assert normalization["canonical_identifier"] == "Prscrbr_NPI"
    assert normalization["column_aliases"] == {
        "PRSCRBR_NPI": "Prscrbr_NPI",
        "Prscrbr_Type_Src": "Prscrbr_Type_src",
    }
    assert normalization["alias_applicability"] == {
        "PRSCRBR_NPI": [2023, 2024],
        "Prscrbr_Type_Src": [2019, 2020, 2021, 2022],
    }
    assert normalization["preserves_raw_source"] is True


def test_inpatient_source_encoding_is_documented() -> None:
    sources = {source["source_id"]: source for source in load_manifest()["sources"]}
    inpatient = sources["cms_inpatient_provider_service"]

    assert inpatient["ingestion_status"] == "silver_complete"
    assert inpatient["schema_normalization"] == {
        "source_encodings": {
            2019: "cp1252",
            2020: "cp1252",
            2021: "cp1252",
            2022: "cp1252",
            2023: "cp1252",
            2024: "utf-8",
        },
        "target_encoding": "utf-8",
        "preserves_raw_source": True,
    }


def test_outpatient_source_encoding_and_period_gaps_are_documented() -> None:
    sources = {source["source_id"]: source for source in load_manifest()["sources"]}
    outpatient = sources["cms_outpatient_provider_service"]

    assert outpatient["ingestion_status"] == "silver_complete"
    assert outpatient["requested_years"] == [2019, 2021, 2023]
    assert outpatient["local_directory"] == (
        "data/raw/cms/cms_outpatient_provider_service"
    )
    assert outpatient["schema_normalization"] == {
        "source_encodings": {
            2019: "cp1252",
            2021: "cp1252",
            2023: "utf-8",
        },
        "target_encoding": "utf-8",
        "preserves_raw_source": True,
    }


def test_physician_service_bronze_contract_is_documented() -> None:
    sources = {source["source_id"]: source for source in load_manifest()["sources"]}
    physician = sources["cms_physician_provider_service"]

    assert physician["ingestion_status"] == "bronze_complete"
    assert physician["requested_years"] == list(range(2019, 2025))
    assert physician["local_directory"] == (
        "data/raw/cms/cms_physician_provider_service"
    )
    assert physician["schema_normalization"] == {
        "source_encodings": {year: "utf-8" for year in range(2019, 2025)},
        "target_encoding": "utf-8",
        "preserves_raw_source": True,
    }
