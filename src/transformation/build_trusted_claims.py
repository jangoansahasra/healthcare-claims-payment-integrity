from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import (
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.synthetic_dimensions import content_hash, load_yaml, table_schema
from src.transformation.trusted_claims import (
    TRUSTED_TABLE_ORDER,
    TrustedClaimsError,
    generate_trusted_rows,
    validate_trusted_rows,
)

DEFAULT_CONTRACT_PATH = Path("config/trusted_claims_contract.yml")


def read_source_rows(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Read the operational and ground-truth inputs required by M04."""
    names = (
        "member",
        "provider",
        "plan",
        "membership_month",
        "claim_header",
        "claim_line",
        "payment_transaction",
        "claim_review",
        "audit_outcome",
        "policy_assignment",
        "anomaly_injection",
    )
    missing = [name for name in names if not (root / f"{name}.parquet").exists()]
    if missing:
        raise TrustedClaimsError("Missing trusted source tables: " + ", ".join(missing))
    return {name: pq.read_table(root / f"{name}.parquet").to_pylist() for name in names}


def build_trusted_claims(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    source_root: Path | None = None,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path | None = None,
) -> dict[str, Any]:
    """Build all twelve trusted tables with deterministic quality evidence."""
    contract = load_yaml(contract_path)
    operational_contract = load_yaml(Path(contract["dataset"]["operational_contract"]))
    anomaly_contract = load_yaml(Path(contract["dataset"]["anomaly_contract"]))
    source_root = source_root or Path(contract["dataset"]["anomalous_source_root"])
    output_root = output_root or Path(contract["dataset"]["trusted_output_root"])
    sample_root = sample_root or Path(contract["dataset"]["publishable_sample_root"])
    quality_report_path = quality_report_path or Path(
        contract["dataset"]["quality_report"]
    )
    source = read_source_rows(source_root)
    trusted = generate_trusted_rows(
        source, contract, operational_contract, anomaly_contract
    )
    checks = validate_trusted_rows(source, trusted, contract)
    table_evidence = {}
    for name in TRUSTED_TABLE_ORDER:
        rows = trusted[name]
        schema = table_schema(contract, name)
        path = output_root / f"{name}.parquet"
        write_parquet_atomic(rows, schema, path)
        write_sample_csv(rows, schema.names, sample_root / f"{name}_sample.csv")
        checks[f"{name}_schema"] = pq.read_schema(path).equals(schema)
        checks[f"{name}_row_count"] = pq.read_metadata(path).num_rows == len(rows)
        table_evidence[name] = {
            "row_count": len(rows),
            "content_sha256": content_hash(rows, schema.names),
            "parquet_size_bytes": path.stat().st_size,
        }
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "contract_version": contract["contract_version"],
        "source_variant": contract["dataset"]["default_source_variant"],
        "deterministic_seed": contract["dataset"]["deterministic_seed"],
        "tables": table_evidence,
        "current_claim_count": sum(
            row["is_current_version"] for row in trusted["fact_claim"]
        ),
        "anomaly_label_count": len(trusted["bridge_claim_anomaly"]),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise TrustedClaimsError("Trusted claims checks failed: " + ", ".join(failed))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the reconciled trusted claims dimensional model."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument("--quality-report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_trusted_claims(
        args.contract,
        args.source_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    print(f"Trusted tables: {len(report['tables'])}")
    print(f"Current claims: {report['current_claim_count']}")
    print(f"Anomaly labels: {report['anomaly_label_count']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
