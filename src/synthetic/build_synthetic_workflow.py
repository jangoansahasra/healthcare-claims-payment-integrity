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
from src.synthetic.synthetic_claims import CLAIM_TABLES, validate_claim_rows
from src.synthetic.synthetic_dimensions import (
    content_hash,
    load_yaml,
    table_schema,
    validate_generated_rows,
)
from src.synthetic.synthetic_workflow import (
    WORKFLOW_TABLES,
    SyntheticWorkflowError,
    generate_workflow_rows,
    validate_workflow_rows,
)

DEFAULT_CONTRACT_PATH = Path("config/synthetic_data_contract.yml")
DEFAULT_GENERATION_CONFIG_PATH = Path("config/synthetic_workflow_generation.yml")
DEFAULT_DATA_ROOT = Path("data/generated/synthetic")
DEFAULT_QUALITY_REPORT_PATH = Path(
    "data/metadata/quality/synthetic_operational_baseline.json"
)
DIMENSION_TABLES = (
    "member",
    "plan",
    "provider",
    "provider_contract",
    "membership_month",
    "policy_assignment",
)


def read_tables(root: Path, names: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    """Read required generated Parquet tables."""
    missing = [name for name in names if not (root / f"{name}.parquet").is_file()]
    if missing:
        raise SyntheticWorkflowError("Missing synthetic inputs: " + ", ".join(missing))
    return {name: pq.read_table(root / f"{name}.parquet").to_pylist() for name in names}


def build_synthetic_workflow(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    generation_config_path: Path = DEFAULT_GENERATION_CONFIG_PATH,
    data_root: Path = DEFAULT_DATA_ROOT,
    sample_root: Path | None = None,
    quality_report_path: Path = DEFAULT_QUALITY_REPORT_PATH,
) -> dict[str, Any]:
    """Complete and validate all 14 clean operational baseline tables."""
    contract = load_yaml(contract_path)
    configuration = load_yaml(generation_config_path)
    sample_root = sample_root or Path(contract["generation"]["publishable_sample_root"])
    dimensions = read_tables(data_root, DIMENSION_TABLES)
    claims = read_tables(data_root, CLAIM_TABLES)
    workflow = generate_workflow_rows(contract, configuration, claims["claim_header"])
    checks = validate_workflow_rows(workflow, claims["claim_header"], contract)

    for table_name, rows in workflow.items():
        schema = table_schema(contract, table_name)
        parquet_path = data_root / f"{table_name}.parquet"
        write_parquet_atomic(rows, schema, parquet_path)
        write_sample_csv(rows, schema.names, sample_root / f"{table_name}_sample.csv")
        checks[f"{table_name}_parquet_schema"] = pq.read_schema(parquet_path).equals(
            schema
        )
        checks[f"{table_name}_parquet_rows"] = pq.read_metadata(
            parquet_path
        ).num_rows == len(rows)

    all_rows = {**dimensions, **claims, **workflow}
    checks.update(
        {
            f"contract_{name}": passed
            for name, passed in validate_generated_rows(all_rows, contract).items()
        }
    )
    checks.update(
        {
            f"claim_{name}": passed
            for name, passed in validate_claim_rows(
                claims, contract, dimensions
            ).items()
        }
    )
    table_reports = {}
    for table_name in contract["tables"]:
        rows = all_rows[table_name]
        schema = table_schema(contract, table_name)
        table_reports[table_name] = {
            "row_count": len(rows),
            "column_count": len(schema.names),
            "content_sha256": content_hash(rows, schema.names),
            "parquet_size_bytes": (data_root / f"{table_name}.parquet").stat().st_size,
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
        "audit_outcome_counts": {
            outcome: sum(row["outcome"] == outcome for row in workflow["audit_outcome"])
            for outcome in sorted({row["outcome"] for row in workflow["audit_outcome"]})
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SyntheticWorkflowError(
            "Synthetic operational quality checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Complete the clean synthetic review and audit workflow."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument(
        "--generation-config", type=Path, default=DEFAULT_GENERATION_CONFIG_PATH
    )
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument(
        "--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT_PATH
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_synthetic_workflow(
        args.contract,
        args.generation_config,
        args.data_root,
        args.sample_root,
        args.quality_report,
    )
    for name in WORKFLOW_TABLES:
        print(f"{name}: {report['tables'][name]['row_count']} rows")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
