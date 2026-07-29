import hashlib
import json
from pathlib import Path

import pytest

from src.ingestion.convert_source_family import (
    build_family_inventory,
    convert_source_family,
    discover_annual_csvs,
    normalized_column_aliases,
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


def test_normalized_column_aliases_selects_observed_source_names(
    tmp_path: Path,
) -> None:
    path = tmp_path / "part_d.csv"
    path.write_text(
        "PRSCRBR_NPI,Tot_Clms\n1000000001,25\n",
        encoding="utf-8",
    )

    aliases = normalized_column_aliases(
        path,
        {"PRSCRBR_NPI": "Prscrbr_NPI"},
    )

    assert aliases == {
        "PRSCRBR_NPI": "Prscrbr_NPI",
    }


def test_normalized_column_aliases_ignores_absent_alias_sources(
    tmp_path: Path,
) -> None:
    path = tmp_path / "part_d.csv"
    path.write_text(
        "Prscrbr_NPI,Tot_Clms\n1000000001,25\n",
        encoding="utf-8",
    )

    aliases = normalized_column_aliases(
        path,
        {"PRSCRBR_NPI": "Prscrbr_NPI"},
    )

    assert aliases == {}


def test_normalized_column_aliases_rejects_target_collision(
    tmp_path: Path,
) -> None:
    path = tmp_path / "part_d.csv"
    path.write_text(
        ("PRSCRBR_NPI,Prscrbr_NPI,Tot_Clms\n1000000001,1000000001,25\n"),
        encoding="utf-8",
    )

    with pytest.raises(
        ConversionError,
        match="alias target already exists",
    ):
        normalized_column_aliases(
            path,
            {"PRSCRBR_NPI": "Prscrbr_NPI"},
        )


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


def test_convert_source_family_applies_per_year_encoding(
    tmp_path: Path,
) -> None:
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    profile_root = tmp_path / "profiles"
    csv_path = raw_root / "inpatient" / "2019" / "inpatient.csv"
    csv_path.parent.mkdir(parents=True)
    content = "CCN,NAME\n670128,Baylor – Pflugerville\n".encode("cp1252")
    csv_path.write_bytes(content)
    receipt_path(csv_path).write_text(
        json.dumps(
            {
                "acquired_at_utc": "2026-07-29T00:00:00+00:00",
                "bytes_downloaded": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    inventory = convert_source_family(
        "inpatient",
        [2019],
        raw_root,
        processed_root,
        profile_root,
        source_encodings={2019: "cp1252"},
    )

    assert inventory["total_row_count"] == 1
    assert inventory["schema_consistent"] is True
