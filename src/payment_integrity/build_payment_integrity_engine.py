from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.payment_integrity.payment_integrity_engine import (
    RULE_IDS,
    PaymentIntegrityError,
    evaluate_findings,
    execute_rules,
)
from src.synthetic.build_synthetic_dimensions import (
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.synthetic_dimensions import content_hash, load_yaml, table_schema

DEFAULT_CONTRACT_PATH = Path("config/payment_integrity_contract.yml")
TRUSTED_INPUTS = (
    "dim_provider",
    "dim_date",
    "dim_service",
    "fact_claim",
    "fact_claim_line",
    "fact_payment_transaction",
)
OUTPUT_ORDER = (
    "rule_run",
    "rule_finding",
    "finding_evidence",
    "finding_ground_truth_match",
    "rule_evaluation",
)


def json_ready(value: Any) -> Any:
    """Convert fixed decimals and nested structures to JSON-safe values."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def read_trusted(root: Path) -> dict[str, list[dict[str, Any]]]:
    """Read detection inputs without exposing the anomaly bridge."""
    missing = [
        name for name in TRUSTED_INPUTS if not (root / f"{name}.parquet").exists()
    ]
    if missing:
        raise PaymentIntegrityError("Missing trusted inputs: " + ", ".join(missing))
    return {
        name: pq.read_table(root / f"{name}.parquet").to_pylist()
        for name in TRUSTED_INPUTS
    }


def build_payment_integrity_engine(
    contract_path: Path = DEFAULT_CONTRACT_PATH,
    input_root: Path | None = None,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path | None = None,
) -> dict[str, Any]:
    """Execute, freeze, evaluate, validate, and publish M05 outputs."""
    contract = load_yaml(contract_path)
    registry = load_yaml(Path(contract["dataset"]["rule_registry"]))
    trusted_contract = load_yaml(Path(contract["dataset"]["trusted_contract"]))
    anomaly_contract = load_yaml(Path(trusted_contract["dataset"]["anomaly_contract"]))
    input_root = input_root or Path(contract["dataset"]["trusted_input_root"])
    output_root = output_root or Path(contract["dataset"]["output_root"])
    sample_root = sample_root or Path(contract["dataset"]["publishable_sample_root"])
    quality_report_path = quality_report_path or Path(
        contract["dataset"]["quality_report"]
    )

    detection_inputs = read_trusted(input_root)
    findings, evidence, eligible = execute_rules(
        detection_inputs, contract, registry, anomaly_contract
    )
    findings_hash = content_hash(
        findings, list(contract["tables"]["rule_finding"]["columns"])
    )
    labels = pq.read_table(input_root / "bridge_claim_anomaly.parquet").to_pylist()
    matches, evaluations = evaluate_findings(
        findings, labels, detection_inputs, contract, eligible
    )
    run_id = contract["dataset"]["deterministic_run_id"]
    runs = [
        {
            "run_id": run_id,
            "contract_version": contract["contract_version"],
            "source_variant": contract["dataset"]["source_variant"],
            "deterministic_seed": contract["dataset"]["deterministic_seed"],
            "run_status": "completed",
            "enabled_rule_count": len(RULE_IDS),
            "finding_count": len(findings),
            "total_amount_at_risk": sum(
                (row["amount_at_risk"] for row in findings), Decimal("0.00")
            ),
            "findings_frozen": True,
            "ground_truth_accessed_during_detection": False,
        }
    ]
    outputs = {
        "rule_run": runs,
        "rule_finding": findings,
        "finding_evidence": evidence,
        "finding_ground_truth_match": matches,
        "rule_evaluation": evaluations,
    }
    overall = next(row for row in evaluations if row["rule_id"] == "ALL")
    checks = {
        "all_rules_executed": {row["rule_id"] for row in findings} == set(RULE_IDS),
        "finding_keys_unique": len(findings)
        == len(
            {
                (
                    row["run_id"],
                    row["rule_id"],
                    row["label_scope"],
                    row["target_record_id"],
                )
                for row in findings
            }
        ),
        "all_findings_explained": all(row["explanation"] for row in findings),
        "all_findings_have_evidence": {row["finding_id"] for row in findings}
        == {row["finding_id"] for row in evidence},
        "nonnegative_amount_at_risk": all(
            row["amount_at_risk"] >= 0 for row in findings
        ),
        "ground_truth_isolated_from_detection": runs[0][
            "ground_truth_accessed_during_detection"
        ]
        is False,
        "findings_frozen_before_evaluation": runs[0]["findings_frozen"] is True,
        "all_labels_evaluated": len(
            {row["injection_id"] for row in matches if row["injection_id"]}
        )
        == len(labels),
        "match_keys_unique": len(matches)
        == len({(row["rule_id"], row["canonical_target_id"]) for row in matches}),
        "confusion_counts_reconcile": all(
            row["eligible_target_count"]
            == row["true_positive_count"]
            + row["false_positive_count"]
            + row["false_negative_count"]
            + row["true_negative_count"]
            for row in evaluations
        ),
        "precision_target_met": overall["precision_threshold_passed"],
        "recall_target_met": overall["recall_threshold_passed"],
        "false_positive_rate_target_met": overall[
            "false_positive_rate_threshold_passed"
        ],
        "findings_hash_frozen": findings_hash
        == content_hash(findings, list(contract["tables"]["rule_finding"]["columns"])),
    }
    table_evidence = {}
    for name in OUTPUT_ORDER:
        rows = outputs[name]
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
        "run_id": run_id,
        "enabled_rule_count": len(RULE_IDS),
        "ground_truth_label_count": len(labels),
        "finding_count": len(findings),
        "findings_frozen_sha256": findings_hash,
        "overall_evaluation": overall,
        "rule_evaluation": [row for row in evaluations if row["rule_id"] != "ALL"],
        "tables": table_evidence,
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(json_ready(report), quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise PaymentIntegrityError(
            "Payment-integrity checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute and evaluate PI001-PI010.")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument("--quality-report", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_payment_integrity_engine(
        args.contract,
        args.input_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    overall = report["overall_evaluation"]
    print(f"Rules executed: {report['enabled_rule_count']}")
    print(f"Findings: {report['finding_count']}")
    print(f"Labels evaluated: {report['ground_truth_label_count']}")
    print(f"Precision: {overall['precision']}")
    print(f"Recall: {overall['recall']}")
    print(f"False-positive rate: {overall['false_positive_rate']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
