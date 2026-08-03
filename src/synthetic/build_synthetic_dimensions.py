from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.synthetic.synthetic_dimensions import (
    SyntheticDimensionError,
    content_hash,
    generate_dimension_rows,
    load_yaml,
    table_schema,
    validate_generated_rows,
)

DEFAULT_CONTRACT_PATH = Path("config/synthetic_data_contract.yml")
DEFAULT_GENERATION_CONFIG_PATH = Path("config/synthetic_dimension_generation.yml")
DEFAULT_QUALITY_REPORT_PATH = Path(
    "data/metadata/quality/synthetic_dimensions_eligibility.json"
)
GENERATED_TABLES = (
    "member",
    "plan",
    "provider",
    "provider_contract",
    "membership_month",
    "policy_assignment",
)


def file_sha256(path: Path) -> str:
    """Return a SHA-256 digest for a configuration file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_parquet_atomic(
    rows: list[dict[str, Any]],
    schema: pa.Schema,
    output_path: Path,
) -> None:
    """Write deterministic rows to compressed Parquet with atomic replacement."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    try:
        table = pa.Table.from_pylist(rows, schema=schema)
        pq.write_table(
            table,
            partial,
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        partial.replace(output_path)
    finally:
        partial.unlink(missing_ok=True)


def csv_value(value: Any) -> Any:
    """Return a stable CSV representation for supported scalar values."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value).lower()
    return value


def write_sample_csv(
    rows: list[dict[str, Any]],
    columns: list[str],
    output_path: Path,
    sample_size: int = 25,
) -> None:
    """Write a small deterministic synthetic-only demonstration sample."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    try:
        with partial.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            for row in rows[:sample_size]:
                writer.writerow({column: csv_value(row[column]) for column in columns})
        partial.replace(output_path)
    finally:
        partial.unlink(missing_ok=True)


def write_json_atomic(payload: dict[str, Any], output_path: Path) -> None:
    """Write machine-readable JSON with atomic replacement."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(output_path.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    partial.replace(output_path)


def build_synthetic_dimensions(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    generation_config_path: Path = DEFAULT_GENERATION_CONFIG_PATH,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path = DEFAULT_QUALITY_REPORT_PATH,
) -> dict[str, Any]:
    """Generate, validate, and write deterministic synthetic dimensions."""
    contract = load_yaml(contract_path)
    configuration = load_yaml(generation_config_path)
    governed_output_root = Path(contract["generation"]["full_output_root"])
    governed_sample_root = Path(contract["generation"]["publishable_sample_root"])
    output_root = output_root or governed_output_root
    sample_root = sample_root or governed_sample_root

    rows_by_table = generate_dimension_rows(contract, configuration)
    if tuple(rows_by_table) != GENERATED_TABLES:
        raise SyntheticDimensionError(
            f"Generated table order mismatch: {tuple(rows_by_table)}"
        )

    checks = validate_generated_rows(rows_by_table, contract)
    member_birth_year = {
        row["member_id"]: row["birth_year"] for row in rows_by_table["member"]
    }
    plan_minimum_ages = {
        plan["plan_id"]: int(plan["minimum_age"]) for plan in configuration["plans"]
    }
    reporting_year = int(str(contract["dataset"]["reporting_start_date"])[:4])
    checks["plan_age_eligibility"] = all(
        reporting_year - member_birth_year[row["member_id"]]
        >= plan_minimum_ages[row["plan_id"]]
        for row in rows_by_table["membership_month"]
    )
    table_reports: dict[str, dict[str, Any]] = {}
    for table_name, rows in rows_by_table.items():
        schema = table_schema(contract, table_name)
        columns = schema.names
        parquet_path = output_root / f"{table_name}.parquet"
        sample_path = sample_root / f"{table_name}_sample.csv"
        write_parquet_atomic(rows, schema, parquet_path)
        write_sample_csv(rows, columns, sample_path)

        observed_schema = pq.read_schema(parquet_path)
        checks[f"{table_name}_parquet_schema"] = observed_schema.equals(schema)
        checks[f"{table_name}_parquet_rows"] = pq.read_metadata(
            parquet_path
        ).num_rows == len(rows)
        table_reports[table_name] = {
            "row_count": len(rows),
            "column_count": len(columns),
            "content_sha256": content_hash(rows, columns),
            "parquet_size_bytes": parquet_path.stat().st_size,
            "sample_row_count": min(25, len(rows)),
        }

    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "contract_version": contract["contract_version"],
        "generation_version": configuration["generation_version"],
        "deterministic_seed": contract["dataset"]["deterministic_seed"],
        "contract_sha256": file_sha256(contract_path),
        "generation_config_sha256": file_sha256(generation_config_path),
        "tables": table_reports,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)

    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SyntheticDimensionError(
            "Synthetic dimension quality checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic dimensions and eligibility."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument(
        "--generation-config",
        type=Path,
        default=DEFAULT_GENERATION_CONFIG_PATH,
    )
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument(
        "--quality-report",
        type=Path,
        default=DEFAULT_QUALITY_REPORT_PATH,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_synthetic_dimensions(
        args.contract,
        args.generation_config,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    for table_name, details in report["tables"].items():
        print(f"{table_name}: {details['row_count']} rows")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
