from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import (
    file_sha256,
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.synthetic_claims import (
    CLAIM_TABLES,
    SyntheticClaimError,
    generate_claim_rows,
    validate_claim_rows,
)
from src.synthetic.synthetic_dimensions import (
    content_hash,
    load_yaml,
    table_schema,
    validate_generated_rows,
)

DEFAULT_CONTRACT_PATH = Path("config/synthetic_data_contract.yml")
DEFAULT_GENERATION_CONFIG_PATH = Path("config/synthetic_claim_generation.yml")
DEFAULT_DIMENSION_ROOT = Path("data/generated/synthetic")
DEFAULT_QUALITY_REPORT_PATH = Path(
    "data/metadata/quality/synthetic_claim_lifecycle.json"
)
DIMENSION_TABLES = (
    "member",
    "plan",
    "provider",
    "provider_contract",
    "membership_month",
    "policy_assignment",
)


def read_dimensions(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Read the validated synthetic dimension Parquet inputs."""
    missing = [
        name for name in DIMENSION_TABLES if not (root / f"{name}.parquet").is_file()
    ]
    if missing:
        raise SyntheticClaimError(
            "Missing synthetic dimension inputs: " + ", ".join(missing)
        )
    return {
        name: pq.read_table(root / f"{name}.parquet").to_pylist()
        for name in DIMENSION_TABLES
    }


def build_synthetic_claims(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    generation_config_path: Path = DEFAULT_GENERATION_CONFIG_PATH,
    dimension_root: Path = DEFAULT_DIMENSION_ROOT,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path = DEFAULT_QUALITY_REPORT_PATH,
) -> dict[str, Any]:
    """Generate and validate the deterministic clean claim lifecycle."""
    contract = load_yaml(contract_path)
    configuration = load_yaml(generation_config_path)
    output_root = output_root or Path(contract["generation"]["full_output_root"])
    sample_root = sample_root or Path(contract["generation"]["publishable_sample_root"])
    dimensions = read_dimensions(dimension_root)
    rows_by_table = generate_claim_rows(contract, configuration, dimensions)
    if tuple(rows_by_table) != CLAIM_TABLES:
        raise SyntheticClaimError(
            f"Generated table order mismatch: {tuple(rows_by_table)}"
        )
    checks = validate_claim_rows(rows_by_table, contract, dimensions)
    contract_checks = validate_generated_rows({**dimensions, **rows_by_table}, contract)
    checks.update(
        {f"contract_{name}": passed for name, passed in contract_checks.items()}
    )
    table_reports: dict[str, dict[str, Any]] = {}
    for table_name, rows in rows_by_table.items():
        schema = table_schema(contract, table_name)
        parquet_path = output_root / f"{table_name}.parquet"
        sample_path = sample_root / f"{table_name}_sample.csv"
        write_parquet_atomic(rows, schema, parquet_path)
        write_sample_csv(rows, schema.names, sample_path)
        checks[f"{table_name}_parquet_schema"] = pq.read_schema(parquet_path).equals(
            schema
        )
        checks[f"{table_name}_parquet_rows"] = pq.read_metadata(
            parquet_path
        ).num_rows == len(rows)
        table_reports[table_name] = {
            "row_count": len(rows),
            "column_count": len(schema.names),
            "content_sha256": content_hash(rows, schema.names),
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
        "claim_type_counts": {
            claim_type: sum(
                row["claim_type"] == claim_type for row in rows_by_table["claim_header"]
            )
            for claim_type in contract["allowed_values"]["claim_type"]
        },
        "claim_status_counts": {
            status: sum(
                row["claim_status"] == status for row in rows_by_table["claim_header"]
            )
            for status in sorted(
                {row["claim_status"] for row in rows_by_table["claim_header"]}
            )
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SyntheticClaimError(
            "Synthetic claim quality checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic clean synthetic claim lifecycle."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument(
        "--generation-config", type=Path, default=DEFAULT_GENERATION_CONFIG_PATH
    )
    parser.add_argument("--dimension-root", type=Path, default=DEFAULT_DIMENSION_ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument(
        "--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT_PATH
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_synthetic_claims(
        args.contract,
        args.generation_config,
        args.dimension_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    for table_name, details in report["tables"].items():
        print(f"{table_name}: {details['row_count']} rows")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
