from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.ingestion.convert_to_parquet import (
    ConversionError,
    convert_csv_to_parquet,
    profile_parquet,
    write_profile,
)
from src.ingestion.download_sources import load_yaml

DEFAULT_ACQUISITION_PATH = Path("config/acquisition.yml")
DEFAULT_RAW_ROOT = Path("data/raw/cms")
DEFAULT_PROCESSED_ROOT = Path("data/processed/cms")
DEFAULT_PROFILE_ROOT = Path("data/metadata/profiles")


def normalized_column_aliases(
    csv_path: Path,
    configured_aliases: dict[str, str] | None,
    source_encoding: str = "utf-8",
) -> dict[str, str]:
    """Return governed aliases applicable to one observed CSV header."""
    if not configured_aliases:
        return {}

    with csv_path.open(
        encoding=source_encoding,
        newline="",
    ) as file:
        header = set(next(csv.reader(file)))

    active_aliases: dict[str, str] = {}

    for source, target in configured_aliases.items():
        if source not in header:
            continue

        if target in header and target != source:
            raise ConversionError(
                "Cannot normalize column alias because alias target "
                f"already exists: {source} -> {target}"
            )

        active_aliases[source] = target

    return active_aliases


def discover_annual_csvs(
    raw_root: Path,
    source_id: str,
    years: list[int],
) -> dict[int, Path]:
    """Find exactly one acquired CSV for every requested source year."""
    discovered: dict[int, Path] = {}

    for year in sorted(years):
        year_directory = raw_root / source_id / str(year)

        if not year_directory.is_dir():
            raise ConversionError(f"Missing raw year directory: {year_directory}")

        csv_files = sorted(
            path
            for path in year_directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".csv"
        )

        if len(csv_files) != 1:
            raise ConversionError(
                f"Expected one CSV in {year_directory}; found {len(csv_files)}"
            )

        discovered[year] = csv_files[0]

    return discovered


def source_schema_signature(profile: dict[str, Any]) -> str:
    """Return a stable signature for source columns before lineage fields."""
    source_columns = [
        {
            "name": column["name"],
            "duckdb_type": column["duckdb_type"],
        }
        for column in profile["columns"]
        if not column["name"].startswith("_")
    ]
    serialized = json.dumps(
        source_columns,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def build_family_inventory(
    source_id: str,
    annual_profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build cross-year row-count and schema-drift metadata."""
    schema_groups: dict[str, dict[str, Any]] = {}
    years: list[dict[str, Any]] = []

    for profile in sorted(
        annual_profiles,
        key=lambda item: item["reporting_year"],
    ):
        signature = source_schema_signature(profile)
        source_column_count = sum(
            not column["name"].startswith("_") for column in profile["columns"]
        )

        schema_group = schema_groups.setdefault(
            signature,
            {
                "schema_signature": signature,
                "source_column_count": source_column_count,
                "years": [],
            },
        )
        schema_group["years"].append(profile["reporting_year"])

        years.append(
            {
                "reporting_year": profile["reporting_year"],
                "row_count": profile["row_count"],
                "source_column_count": source_column_count,
                "parquet_path": profile["parquet_path"],
                "parquet_size_bytes": profile["size_bytes"],
                "parquet_sha256": profile["sha256"],
                "schema_signature": signature,
            }
        )

    return {
        "family_inventory_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_id": source_id,
        "year_count": len(years),
        "reporting_years": [item["reporting_year"] for item in years],
        "total_row_count": sum(item["row_count"] for item in years),
        "schema_group_count": len(schema_groups),
        "schema_consistent": len(schema_groups) == 1,
        "schema_groups": sorted(
            schema_groups.values(),
            key=lambda item: item["schema_signature"],
        ),
        "years": years,
    }


def convert_source_family(
    source_id: str,
    years: list[int],
    raw_root: Path = DEFAULT_RAW_ROOT,
    processed_root: Path = DEFAULT_PROCESSED_ROOT,
    profile_root: Path = DEFAULT_PROFILE_ROOT,
    column_aliases: dict[str, str] | None = None,
    source_encodings: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Convert and profile all requested annual files for one source."""
    annual_csvs = discover_annual_csvs(
        raw_root,
        source_id,
        years,
    )
    annual_profiles: list[dict[str, Any]] = []

    for year, csv_path in annual_csvs.items():
        source_encoding = (source_encodings or {}).get(year, "utf-8")
        parquet_path = (
            processed_root / source_id / str(year) / f"{source_id}_{year}.parquet"
        )
        profile_path = profile_root / f"{source_id}_{year}.json"
        active_aliases = normalized_column_aliases(
            csv_path,
            column_aliases,
            source_encoding,
        )

        convert_csv_to_parquet(
            csv_path,
            parquet_path,
            source_id,
            year,
            active_aliases,
            source_encoding,
        )
        profile = profile_parquet(
            parquet_path,
            source_id,
            year,
        )
        write_profile(profile, profile_path)
        annual_profiles.append(profile)

        print(
            f"Converted {source_id} {year}: "
            f"{profile['row_count']} rows, "
            f"{profile['size_bytes'] / (1024**2):.2f} MiB"
        )

    inventory = build_family_inventory(
        source_id,
        annual_profiles,
    )
    inventory_path = profile_root / f"{source_id}_family.json"
    write_profile(inventory, inventory_path)

    print(
        f"Family inventory: {inventory['total_row_count']} rows, "
        f"{inventory['schema_group_count']} schema group(s)"
    )
    print(f"Inventory written to {inventory_path}")

    return inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert one governed annual CMS source family."
    )
    parser.add_argument("--source-id", required=True)
    parser.add_argument(
        "--year",
        action="append",
        type=int,
        help="Reporting year to convert; repeat for multiple years.",
    )
    parser.add_argument(
        "--acquisition-config",
        type=Path,
        default=DEFAULT_ACQUISITION_PATH,
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=DEFAULT_PROCESSED_ROOT,
    )
    parser.add_argument(
        "--profile-root",
        type=Path,
        default=DEFAULT_PROFILE_ROOT,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    acquisition = load_yaml(args.acquisition_config)
    strategies = acquisition["source_strategies"]

    if args.source_id not in strategies:
        raise ConversionError(
            f"Source is not configured for acquisition: {args.source_id}"
        )

    years = args.year or strategies[args.source_id]["years"]

    convert_source_family(
        args.source_id,
        years,
        args.raw_root,
        args.processed_root,
        args.profile_root,
        strategies[args.source_id].get("column_aliases"),
        strategies[args.source_id].get("source_encodings"),
    )


if __name__ == "__main__":
    main()
