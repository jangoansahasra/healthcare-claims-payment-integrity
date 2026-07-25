from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

CMS_CATALOG_URL = "https://data.cms.gov/data.json"
USER_AGENT = "healthcare-claims-payment-integrity/1.0"


class CatalogResolutionError(ValueError):
    """Raised when a CMS dataset or annual distribution cannot be resolved."""


def fetch_catalog(
    url: str = CMS_CATALOG_URL,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Download the official machine-readable CMS data catalog."""
    request = Request(url, headers={"User-Agent": USER_AGENT})

    with urlopen(request, timeout=timeout_seconds) as response:
        catalog = json.load(response)

    if not isinstance(catalog, dict):
        raise CatalogResolutionError("CMS catalog root must be a JSON object")

    if not isinstance(catalog.get("dataset"), list):
        raise CatalogResolutionError("CMS catalog must contain a dataset list")

    return catalog


def find_dataset(catalog: dict[str, Any], title: str) -> dict[str, Any]:
    """Return the unique CMS catalog dataset matching an exact title."""
    datasets = catalog.get("dataset")

    if not isinstance(datasets, list):
        raise CatalogResolutionError("CMS catalog must contain a dataset list")

    matches = [
        dataset
        for dataset in datasets
        if isinstance(dataset, dict)
        and str(dataset.get("title", "")).casefold() == title.casefold()
    ]

    if not matches:
        raise CatalogResolutionError(f"CMS dataset not found: {title}")

    if len(matches) > 1:
        raise CatalogResolutionError(f"CMS dataset title is not unique: {title}")

    return matches[0]


def distribution_year(distribution: dict[str, Any]) -> int | None:
    """Extract the reporting year from a CMS distribution temporal value."""
    temporal = str(distribution.get("temporal", ""))

    if len(temporal) >= 4 and temporal[:4].isdigit():
        return int(temporal[:4])

    return None


def csv_distributions(
    dataset: dict[str, Any],
    year: int,
) -> list[dict[str, Any]]:
    """Return downloadable CSV distributions matching a reporting year."""
    distributions = dataset.get("distribution", [])

    if not isinstance(distributions, list):
        raise CatalogResolutionError("Dataset distribution must be a list")

    return [
        distribution
        for distribution in distributions
        if isinstance(distribution, dict)
        and str(distribution.get("format", "")).upper() == "CSV"
        and distribution.get("downloadURL")
        and distribution_year(distribution) == year
    ]


def resource_identifier(distribution: dict[str, Any]) -> str:
    """Extract the version-specific CMS resource identifier."""
    resources_api = str(distribution.get("resourcesAPI", "")).rstrip("/")

    if not resources_api:
        raise CatalogResolutionError("Distribution is missing resourcesAPI")

    return resources_api.rsplit("/", maxsplit=1)[-1]


def resolve_csv_distribution(
    catalog: dict[str, Any],
    dataset_title: str,
    year: int,
) -> dict[str, Any]:
    """Resolve acquisition metadata for one CMS dataset reporting year."""
    dataset = find_dataset(catalog, dataset_title)
    matches = csv_distributions(dataset, year)

    if not matches:
        raise CatalogResolutionError(
            f"No CSV distribution found for {dataset_title}, year {year}"
        )

    selected = sorted(
        matches,
        key=lambda distribution: str(distribution.get("modified", "")),
        reverse=True,
    )[0]

    return {
        "dataset_title": dataset["title"],
        "reporting_year": year,
        "download_url": selected["downloadURL"],
        "resource_identifier": resource_identifier(selected),
        "modified": selected.get("modified"),
        "temporal": selected.get("temporal"),
        "license": dataset.get("license"),
        "landing_page": dataset.get("landingPage"),
        "catalog_identifier": dataset.get("identifier"),
    }
