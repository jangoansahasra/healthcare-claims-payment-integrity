from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb

from src.ingestion.download_sources import (
    receipt_path,
    verified_existing_file,
)

DEFAULT_PROFILE_DIRECTORY = Path("data/metadata/profiles")
HASH_CHUNK_SIZE = 8 * 1024 * 1024


class ConversionError(RuntimeError):
    """Raised when a governed source cannot be converted safely."""


def sql_literal(value: str | Path) -> str:
    """Return a safely escaped DuckDB SQL string literal."""
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def quote_identifier(value: str) -> str:
    """Return a safely escaped DuckDB identifier."""
    return '"' + value.replace('"', '""') + '"'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)

    return digest.hexdigest()


def convert_csv_to_parquet(
    input_path: Path,
    output_path: Path,
    source_id: str,
    reporting_year: int,
    column_aliases: dict[str, str] | None = None,
) -> None:
    """Convert a verified raw CSV to string-preserving Zstandard Parquet."""
    if not verified_existing_file(input_path):
        raise ConversionError(
            f"Raw file does not match a valid acquisition receipt: {input_path}"
        )

    receipt = json.loads(receipt_path(input_path).read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_sql = sql_literal(input_path)
    output_sql = sql_literal(output_path)
    source_id_sql = sql_literal(source_id)
    source_file_sql = sql_literal(input_path.name)
    acquired_at_sql = sql_literal(receipt["acquired_at_utc"])
    projection = "*"

    if column_aliases:
        rename_items = ", ".join(
            f"{quote_identifier(source)} AS {quote_identifier(target)}"
            for source, target in column_aliases.items()
        )
        projection = f"* RENAME ({rename_items})"
    query = f"""
        COPY (
            SELECT
                {projection},
                {source_id_sql} AS _source_id,
                {reporting_year} AS _reporting_year,
                {source_file_sql} AS _source_file,
                {acquired_at_sql} AS _acquired_at_utc
            FROM read_csv(
                {input_sql},
                header = true,
                all_varchar = true,
                strict_mode = true
            )
        )
        TO {output_sql}
        (
            FORMAT PARQUET,
            COMPRESSION ZSTD,
            ROW_GROUP_SIZE 100000
        )
    """

    with duckdb.connect() as connection:
        connection.execute(query)


def profile_parquet(
    parquet_path: Path,
    source_id: str,
    reporting_year: int,
) -> dict[str, Any]:
    """Create a technical profile for one Parquet artifact."""
    parquet_sql = sql_literal(parquet_path)

    with duckdb.connect() as connection:
        row_count = connection.execute(
            f"SELECT COUNT(*) FROM read_parquet({parquet_sql})"
        ).fetchone()[0]
        schema_rows = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet({parquet_sql})"
        ).fetchall()

    columns = [
        {
            "name": row[0],
            "duckdb_type": row[1],
            "nullable": row[2],
        }
        for row in schema_rows
    ]

    return {
        "profile_version": 1,
        "source_id": source_id,
        "reporting_year": reporting_year,
        "parquet_path": str(parquet_path),
        "row_count": row_count,
        "column_count": len(columns),
        "size_bytes": parquet_path.stat().st_size,
        "sha256": sha256_file(parquet_path),
        "compression": "zstd",
        "source_values_preserved_as_strings": True,
        "columns": columns,
    }


def write_profile(profile: dict[str, Any], profile_path: Path) -> None:
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a verified CMS CSV to bronze Parquet."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--reporting-year", type=int, required=True)
    parser.add_argument(
        "--profile-output",
        type=Path,
        required=True,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    convert_csv_to_parquet(
        args.input,
        args.output,
        args.source_id,
        args.reporting_year,
    )
    profile = profile_parquet(
        args.output,
        args.source_id,
        args.reporting_year,
    )
    write_profile(profile, args.profile_output)

    print(f"Converted rows: {profile['row_count']}")
    print(f"Parquet columns: {profile['column_count']}")
    print(f"Parquet size: {profile['size_bytes'] / (1024**2):.2f} MiB")
    print(f"Profile written to {args.profile_output}")


if __name__ == "__main__":
    main()
