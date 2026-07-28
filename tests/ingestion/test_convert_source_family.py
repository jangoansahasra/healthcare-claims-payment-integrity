import hashlib
import json
from pathlib import Path

import pytest

from src.ingestion.convert_source_family import (
    build_family_inventory,
    convert_source_family,
    discover_annual_csvs,
)
from src.ingestion.convert_to_parquet import ConversionError
from src.ingestion.download_sources import receipt_path


def create_verified_csv(path: Path, rows: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "NPI,AMOUNT\n" + "".join(f"{npi},{amount}\n" for npi, amount in rows)
    encoded = content.encode()
    path.write_bytes(encoded)

    receipt = {
        "acquired_at_utc": "2026-07-27T00:00:00+00:00",
        "bytes_downloaded": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    receipt_path(path).write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )


def example_profile(
    year: int,
    source_columns: list[str],
) -> dict:
    columns = [
        {
            "name": column,
            "duckdb_type": "VARCHAR",
            "nullable": "YES",
        }
        for column in source_columns
    ]
    columns.extend(
        [
            {
                "name": "_source_id",
                "duckdb_type": "VARCHAR",
                "nullable": "YES",
            },
            {
                "name": "_reporting_year",
                "duckdb_type": "INTEGER",
                "nullable": "YES",
            },
        ]
    )

    return {
        "reporting_year": year,
        "row_count": 10,
        "parquet_path": f"example/{year}.parquet",
        "size_bytes": 100,
        "sha256": f"sha-{year}",
        "columns": columns,
    }


def test_discover_annual_csvs_accepts_case_insensitive_suffix(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "example_source"
    csv_2019 = source_root / "2019" / "example.csv"
    csv_2020 = source_root / "2020" / "example.CSV"
    csv_2019.parent.mkdir(parents=True)
    csv_2020.parent.mkdir(parents=True)
    csv_2019.touch()
    csv_2020.touch()

    discovered = discover_annual_csvs(
        tmp_path,
        "example_source",
        [2019, 2020],
    )

    assert discovered == {
        2019: csv_2019,
        2020: csv_2020,
    }


def test_discover_annual_csvs_requires_every_year(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConversionError, match="Missing raw year"):
        discover_annual_csvs(
            tmp_path,
            "example_source",
            [2019],
        )


def test_discover_annual_csvs_rejects_multiple_csv_files(
    tmp_path: Path,
) -> None:
    year_directory = tmp_path / "example_source" / "2019"
    year_directory.mkdir(parents=True)
    (year_directory / "one.csv").touch()
    (year_directory / "two.csv").touch()

    with pytest.raises(ConversionError, match="Expected one CSV"):
        discover_annual_csvs(
            tmp_path,
            "example_source",
            [2019],
        )


def test_family_inventory_identifies_consistent_schema() -> None:
    profiles = [
        example_profile(2019, ["NPI", "AMOUNT"]),
        example_profile(2020, ["NPI", "AMOUNT"]),
    ]

    inventory = build_family_inventory(
        "example_source",
        profiles,
    )

    assert inventory["reporting_years"] == [2019, 2020]
    assert inventory["total_row_count"] == 20
    assert inventory["schema_group_count"] == 1
    assert inventory["schema_consistent"] is True
    assert inventory["schema_groups"][0]["years"] == [2019, 2020]


def test_family_inventory_detects_schema_drift() -> None:
    profiles = [
        example_profile(2019, ["NPI", "AMOUNT"]),
        example_profile(2020, ["NPI", "AMOUNT", "NEW_FIELD"]),
    ]

    inventory = build_family_inventory(
        "example_source",
        profiles,
    )

    assert inventory["schema_group_count"] == 2
    assert inventory["schema_consistent"] is False


def test_convert_source_family_end_to_end(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    profile_root = tmp_path / "profiles"

    create_verified_csv(
        raw_root / "example_source" / "2019" / "example.csv",
        [("0000000001", "10.25"), ("0000000002", "20.50")],
    )
    create_verified_csv(
        raw_root / "example_source" / "2020" / "example.csv",
        [("0000000001", "11.00"), ("0000000003", "30.00")],
    )

    inventory = convert_source_family(
        "example_source",
        [2019, 2020],
        raw_root,
        processed_root,
        profile_root,
    )

    assert inventory["year_count"] == 2
    assert inventory["total_row_count"] == 4
    assert inventory["schema_consistent"] is True
    assert (
        processed_root / "example_source" / "2019" / "example_source_2019.parquet"
    ).exists()
    assert (profile_root / "example_source_2019.json").exists()
    assert (profile_root / "example_source_family.json").exists()
