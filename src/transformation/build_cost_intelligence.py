from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import (
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.synthetic_dimensions import content_hash, load_yaml, table_schema
from src.transformation.cost_intelligence import (
    OUTPUT_ORDER,
    CostIntelligenceError,
    generate_cost_intelligence,
    validate_cost_intelligence,
)

DEFAULT_CONTRACT_PATH = Path("config/cost_intelligence_contract.yml")
INPUTS = (
    "dim_date",
    "dim_service",
    "fact_membership_month",
    "fact_claim",
    "fact_claim_line",
    "fact_payment_transaction",
)


def read_trusted(root: Path) -> dict[str, list[dict[str, Any]]]:
    missing = [name for name in INPUTS if not (root / f"{name}.parquet").exists()]
    if missing:
        raise CostIntelligenceError("Missing trusted inputs: " + ", ".join(missing))
    return {
        name: pq.read_table(root / f"{name}.parquet").to_pylist() for name in INPUTS
    }


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def build_cost_intelligence(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    input_root: Path | None = None,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path | None = None,
) -> dict[str, Any]:
    contract = load_yaml(contract_path)
    input_root = input_root or Path(contract["dataset"]["trusted_input_root"])
    output_root = output_root or Path(contract["dataset"]["output_root"])
    sample_root = sample_root or Path(contract["dataset"]["publishable_sample_root"])
    quality_report_path = quality_report_path or Path(
        contract["dataset"]["quality_report"]
    )
    source = read_trusted(input_root)
    outputs = generate_cost_intelligence(source, contract)
    checks = validate_cost_intelligence(source, outputs)
    evidence = {}
    for name in OUTPUT_ORDER:
        rows = outputs[name]
        schema = table_schema(contract, name)
        path = output_root / f"{name}.parquet"
        write_parquet_atomic(rows, schema, path)
        write_sample_csv(rows, schema.names, sample_root / f"{name}_sample.csv")
        checks[f"{name}_schema"] = pq.read_schema(path).equals(schema)
        checks[f"{name}_row_count"] = pq.read_metadata(path).num_rows == len(rows)
        evidence[name] = {
            "row_count": len(rows),
            "content_sha256": content_hash(rows, schema.names),
            "parquet_size_bytes": path.stat().st_size,
        }
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "contract_version": contract["contract_version"],
        "ground_truth_accessed": False,
        "tables": evidence,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(_json(report), quality_report_path)
    if not report["all_checks_passed"]:
        raise CostIntelligenceError(
            "Cost-intelligence checks failed: "
            + ", ".join(sorted(name for name, passed in checks.items() if not passed))
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build governed M06 cost-intelligence outputs."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument("--quality-report", type=Path)
    args = parser.parse_args()
    report = build_cost_intelligence(
        args.contract,
        args.input_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    print(f"Cost-intelligence tables: {len(report['tables'])}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
