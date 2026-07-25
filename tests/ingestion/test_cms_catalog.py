import pytest

from src.ingestion.cms_catalog import (
    CatalogResolutionError,
    csv_distributions,
    distribution_year,
    find_dataset,
    resolve_csv_distribution,
    resource_identifier,
)

DATASET_TITLE = "Example CMS Provider Dataset"

CATALOG_FIXTURE = {
    "dataset": [
        {
            "title": DATASET_TITLE,
            "license": "https://www.usa.gov/government-works",
            "landingPage": "https://data.cms.gov/example",
            "identifier": (
                "https://data.cms.gov/data-api/v1/dataset/latest-version/data-viewer"
            ),
            "distribution": [
                {
                    "format": "API",
                    "accessURL": (
                        "https://data.cms.gov/data-api/v1/dataset/latest-version/data"
                    ),
                    "temporal": "2024-01-01/2024-12-31",
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
            ],
        }
    ]
}


def test_find_dataset_returns_exact_title_match() -> None:
    dataset = find_dataset(CATALOG_FIXTURE, DATASET_TITLE.lower())

    assert dataset["title"] == DATASET_TITLE


def test_find_dataset_rejects_unknown_title() -> None:
    with pytest.raises(CatalogResolutionError, match="not found"):
        find_dataset(CATALOG_FIXTURE, "Unknown dataset")


def test_distribution_year_uses_temporal_start() -> None:
    distribution = {"temporal": "2024-01-01/2024-12-31"}

    assert distribution_year(distribution) == 2024
    assert distribution_year({}) is None


def test_csv_distributions_exclude_api_and_other_years() -> None:
    dataset = find_dataset(CATALOG_FIXTURE, DATASET_TITLE)
    matches = csv_distributions(dataset, 2024)

    assert len(matches) == 1
    assert matches[0]["downloadURL"].endswith("example-2024.csv")


def test_resource_identifier_uses_resources_api() -> None:
    distribution = {
        "resourcesAPI": (
            "https://data.cms.gov/data-api/v1/dataset-resources/version-2024"
        )
    }

    assert resource_identifier(distribution) == "version-2024"


def test_resource_identifier_requires_resources_api() -> None:
    with pytest.raises(CatalogResolutionError, match="resourcesAPI"):
        resource_identifier({})


def test_resolve_csv_distribution_returns_governed_metadata() -> None:
    resolved = resolve_csv_distribution(
        CATALOG_FIXTURE,
        DATASET_TITLE,
        2024,
    )

    assert resolved == {
        "dataset_title": DATASET_TITLE,
        "reporting_year": 2024,
        "download_url": "https://data.cms.gov/example-2024.csv",
        "resource_identifier": "version-2024",
        "modified": "2026-05-21",
        "temporal": "2024-01-01/2024-12-31",
        "license": "https://www.usa.gov/government-works",
        "landing_page": "https://data.cms.gov/example",
        "catalog_identifier": (
            "https://data.cms.gov/data-api/v1/dataset/latest-version/data-viewer"
        ),
    }


def test_resolve_csv_distribution_rejects_missing_year() -> None:
    with pytest.raises(CatalogResolutionError, match="No CSV distribution"):
        resolve_csv_distribution(CATALOG_FIXTURE, DATASET_TITLE, 2022)
