from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "config" / "source_manifest.yml"
ACQUISITION_PATH = PROJECT_ROOT / "config" / "acquisition.yml"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(content, dict)
    return content


def test_acquisition_sources_exist_in_manifest() -> None:
    manifest = load_yaml(MANIFEST_PATH)
    acquisition = load_yaml(ACQUISITION_PATH)
    manifest_ids = {source["source_id"] for source in manifest["sources"]}

    assert set(acquisition["source_strategies"]) <= manifest_ids


def test_api_page_size_respects_cms_limit() -> None:
    controls = load_yaml(ACQUISITION_PATH)["global_controls"]

    assert 1 <= controls["api_page_size"] <= 5000


def test_data_publication_controls_are_disabled() -> None:
    controls = load_yaml(ACQUISITION_PATH)["global_controls"]

    assert controls["commit_raw_data"] is False
    assert controls["commit_processed_data"] is False
    assert controls["require_checksum"] is True


def test_full_download_candidates_respect_requested_years() -> None:
    manifest = load_yaml(MANIFEST_PATH)
    acquisition = load_yaml(ACQUISITION_PATH)
    manifest_years = {
        source["source_id"]: set(source["requested_years"])
        for source in manifest["sources"]
    }

    for source_id, strategy in acquisition["source_strategies"].items():
        assert set(strategy["years"]) <= manifest_years[source_id]


def test_complete_detail_sources_use_full_download() -> None:
    strategies = load_yaml(ACQUISITION_PATH)["source_strategies"]

    assert strategies["cms_physician_provider_service"]["strategy"] == "full_download"
    assert strategies["cms_part_d_provider_drug"]["strategy"] == "full_download"
    assert strategies["cms_physician_provider_service"]["years"] == [
        2019,
        2020,
        2021,
        2022,
        2023,
        2024,
    ]
    assert strategies["cms_part_d_provider_drug"]["years"] == [
        2019,
        2020,
        2021,
        2022,
        2023,
        2024,
    ]


def test_disk_safety_controls_are_configured() -> None:
    controls = load_yaml(ACQUISITION_PATH)["global_controls"]

    assert controls["maximum_planned_local_raw_gib"] <= 70
    assert controls["minimum_required_free_disk_gib"] >= 100
