import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from src.ingestion.convert_to_parquet import (
    ConversionError,
    convert_csv_to_parquet,
    profile_parquet,
    sql_literal,
)
from src.ingestion.download_sources import receipt_path


def create_verified_csv(path: Path) -> None:
    content = b"CODE,AMOUNT\nA,10.25\nB,*\n"
    path.write_bytes(content)
    receipt = {
        "acquired_at_utc": "2026-07-25T00:00:00+00:00",
        "bytes_downloaded": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    receipt_path(path).write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )


def test_sql_literal_escapes_single_quotes() -> None:
    assert sql_literal("example's.csv") == "'example''s.csv'"


def test_convert_csv_to_parquet_preserves_source_strings(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "source.csv"
    output_path = tmp_path / "bronze" / "source.parquet"
    create_verified_csv(input_path)

    convert_csv_to_parquet(
        input_path,
        output_path,
        "example_source",
        2024,
    )

    with duckdb.connect() as connection:
        rows = connection.execute(
            """
            SELECT CODE, AMOUNT, _source_id, _reporting_year
            FROM read_parquet(?)
            ORDER BY CODE
            """,
            [str(output_path)],
        ).fetchall()

    assert rows == [
        ("A", "10.25", "example_source", 2024),
        ("B", "*", "example_source", 2024),
    ]


def test_convert_csv_to_parquet_requires_verified_receipt(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "source.csv"
    output_path = tmp_path / "source.parquet"
    input_path.write_text("CODE\nA\n", encoding="utf-8")

    with pytest.raises(ConversionError, match="valid acquisition receipt"):
        convert_csv_to_parquet(
            input_path,
            output_path,
            "example_source",
            2024,
        )


def test_profile_parquet_reports_rows_and_columns(tmp_path: Path) -> None:
    input_path = tmp_path / "source.csv"
    output_path = tmp_path / "source.parquet"
    create_verified_csv(input_path)
    convert_csv_to_parquet(
        input_path,
        output_path,
        "example_source",
        2024,
    )

    profile = profile_parquet(
        output_path,
        "example_source",
        2024,
    )

    assert profile["row_count"] == 2
    assert profile["column_count"] == 6
    assert profile["compression"] == "zstd"
    assert profile["source_values_preserved_as_strings"] is True
