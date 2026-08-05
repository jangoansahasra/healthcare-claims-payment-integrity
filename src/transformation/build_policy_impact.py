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
from src.transformation.policy_impact import (
    OUTPUT_ORDER,
    PolicyImpactError,
    build_provider_month_panel,
    estimate_policy_impact,
    validate_policy_impact,
)

DEFAULT_CONTRACT_PATH = Path("config/policy_impact_contract.yml")
INPUTS = (
    "dim_date",
    "fact_membership_month",
    "fact_claim",
    "fact_claim_review",
    "bridge_provider_policy",
)


def read_inputs(root: Path) -> dict[str, list[dict[str, Any]]]:
    missing = [name for name in INPUTS if not (root / f"{name}.parquet").exists()]
    if missing:
        raise PolicyImpactError("Missing policy inputs: " + ", ".join(missing))
    return {
        name: pq.read_table(root / f"{name}.parquet").to_pylist() for name in INPUTS
    }


def _json(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def build_policy_impact(
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
    source = read_inputs(input_root)
    outputs = estimate_policy_impact(
        build_provider_month_panel(source, contract), contract
    )
    checks = validate_policy_impact(outputs)
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
        raise PolicyImpactError(
            "Policy checks failed: "
            + ", ".join(sorted(k for k, v in checks.items() if not v))
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and diagnose M07 policy impact."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument("--quality-report", type=Path)
    args = parser.parse_args()
    report = build_policy_impact(
        args.contract,
        args.input_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    print(f"Policy-impact tables: {len(report['tables'])}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
