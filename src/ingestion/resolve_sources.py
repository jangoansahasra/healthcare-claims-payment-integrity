from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from src.ingestion.cms_catalog import (
    CMS_CATALOG_URL,
    fetch_catalog,
    resolve_csv_distribution,
)

DEFAULT_MANIFEST_PATH = Path("config/source_manifest.yml")
DEFAULT_OUTPUT_PATH = Path("data/metadata/cms_source_resolution.json")


def load_manifest(path: Path) -> dict[str, Any]:
    """Load the governed source manifest."""
    with path.open(encoding="utf-8") as file:
        manifest = yaml.safe_load(file)

    if not isinstance(manifest, dict):
        raise ValueError("Source manifest root must be a mapping")

    return manifest


def resolve_manifest_sources(
    manifest: dict[str, Any],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve all catalog-backed source years from the CMS catalog."""
    resolved_sources: list[dict[str, Any]] = []

    for source in manifest["sources"]:
        if source["download_method"] != "cms_data_api_catalog":
            continue

        for year in source["requested_years"]:
            resolved = resolve_csv_distribution(
                catalog,
                source["catalog_title"],
                year,
            )
            resolved_sources.append(
                {
                    "source_id": source["source_id"],
                    "domain": source["domain"],
                    **resolved,
                }
            )

    return sorted(
        resolved_sources,
        key=lambda item: (item["source_id"], item["reporting_year"]),
    )


def build_resolution_document(
    manifest: dict[str, Any],
    resolved_sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the persisted acquisition-metadata document."""
    return {
        "resolution_version": 1,
        "resolved_at_utc": datetime.now(UTC).isoformat(),
        "manifest_version": manifest["manifest_version"],
        "manifest_last_reviewed": str(manifest["last_reviewed"]),
        "catalog_url": CMS_CATALOG_URL,
        "resolved_source_count": len(resolved_sources),
        "sources": resolved_sources,
    }


def write_resolution_document(
    document: dict[str, Any],
    output_path: Path,
) -> None:
    """Write acquisition metadata as formatted JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve governed CMS source distributions."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
        help="Path to the YAML source manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path for resolved source metadata.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    catalog = fetch_catalog()
    resolved_sources = resolve_manifest_sources(manifest, catalog)
    document = build_resolution_document(manifest, resolved_sources)
    write_resolution_document(document, args.output)

    print(f"Resolved {len(resolved_sources)} CMS distributions")
    print(f"Metadata written to {args.output}")


if __name__ == "__main__":
    main()
