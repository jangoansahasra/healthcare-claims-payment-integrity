import json
from pathlib import Path

from src.ingestion.resolve_sources import (
    build_resolution_document,
    resolve_manifest_sources,
    write_resolution_document,
)

CATALOG_TITLE = "Example Provider Dataset"

MANIFEST_FIXTURE = {
    "manifest_version": 1,
    "last_reviewed": "2026-07-25",
    "sources": [
        {
            "source_id": "example_provider",
            "domain": "professional_medical",
            "download_method": "cms_data_api_catalog",
            "catalog_title": CATALOG_TITLE,
            "requested_years": [2023, 2024],
        },
        {
            "source_id": "example_reference",
            "domain": "diagnosis",
            "download_method": "reviewed_direct_download",
            "requested_years": [2026],
        },
    ],
}

CATALOG_FIXTURE = {
    "dataset": [
        {
            "title": CATALOG_TITLE,
            "license": "https://www.usa.gov/government-works",
            "landingPage": "https://data.cms.gov/example",
            "identifier": "https://data.cms.gov/example/data-viewer",
            "distribution": [
                {
                    "format": "CSV",
                    "downloadURL": "https://data.cms.gov/example-2023.csv",
                    "resourcesAPI": (
                        "https://data.cms.gov/data-api/v1/"
                        "dataset-resources/version-2023"
                    ),
                    "modified": "2025-05-21",
                    "temporal": "2023-01-01/2023-12-31",
                },
                {
                    "format": "CSV",
                    "downloadURL": "https://data.cms.gov/example-2024.csv",
                    "resourcesAPI": (
                        "https://data.cms.gov/data-api/v1/"
                        "dataset-resources/version-2024"
                    ),
                    "modified": "2026-05-21",
                    "temporal": "2024-01-01/2024-12-31",
                },
            ],
        }
    ]
}


def test_resolve_manifest_sources_resolves_only_catalog_sources() -> None:
    resolved = resolve_manifest_sources(MANIFEST_FIXTURE, CATALOG_FIXTURE)

    assert len(resolved) == 2
    assert {item["reporting_year"] for item in resolved} == {2023, 2024}
    assert all(item["source_id"] == "example_provider" for item in resolved)


def test_build_resolution_document_records_provenance() -> None:
    resolved = resolve_manifest_sources(MANIFEST_FIXTURE, CATALOG_FIXTURE)
    document = build_resolution_document(MANIFEST_FIXTURE, resolved)

    assert document["resolution_version"] == 1
    assert document["manifest_version"] == 1
    assert document["manifest_last_reviewed"] == "2026-07-25"
    assert document["resolved_source_count"] == 2
    assert document["catalog_url"] == "https://data.cms.gov/data.json"
    assert document["resolved_at_utc"]


def test_write_resolution_document_creates_json(tmp_path: Path) -> None:
    output_path = tmp_path / "metadata" / "resolved.json"
    document = {
        "resolution_version": 1,
        "resolved_source_count": 0,
        "sources": [],
    }

    write_resolution_document(document, output_path)

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == document
