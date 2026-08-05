from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import write_json_atomic
from src.synthetic.synthetic_dimensions import load_yaml

DEFAULT_CONTRACT = Path("config/sas_reconciliation_contract.yml")
INPUT_TABLES = {
    "fact_claim": "trusted",
    "fact_membership_month": "trusted",
    "monthly_cost_utilization": "cost",
    "rule_finding": "payment",
    "provider_month_policy_panel": "policy",
    "policy_effect_estimate": "policy",
}


def scan_sas_log(text: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Apply governed error and warning patterns to a real SAS log's text."""
    policy = contract["log_policy"]
    failures = [
        pattern
        for pattern in policy["fail_patterns"]
        if pattern.lower() in text.lower()
    ]
    reviews = [
        pattern
        for pattern in policy["review_patterns"]
        if pattern.lower() in text.lower()
    ]
    passed = not failures and (
        not reviews or policy["unintended_conversion_warnings_allowed"]
    )
    return {"failures": failures, "review_patterns": reviews, "passed": passed}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: _text(value) for key, value in row.items()} for row in rows
        )


def _reference_rows(
    tables: dict[str, list[dict[str, Any]]], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    claims = tables["fact_claim"]
    current_paid = [
        row
        for row in claims
        if row["is_current_version"] and row["claim_status"] == "paid"
    ]
    membership = tables["fact_membership_month"]
    cost = tables["monthly_cost_utilization"]
    findings = tables["rule_finding"]
    panel = tables["provider_month_policy_panel"]
    effects = [
        row
        for row in tables["policy_effect_estimate"]
        if row["specification"] == "balanced_panel"
    ]
    tolerance = contract["tolerances"]
    rows: list[dict[str, Any]] = []

    def add(
        metric: str, scope: str, value: Any, kind: str, source: str, key: str
    ) -> None:
        rows.append(
            {
                "metric_id": metric,
                "comparison_scope": scope,
                "metric_type": kind,
                "python_value": value,
                "tolerance": tolerance[key],
                "source_table": source,
                "formula_version": 1,
            }
        )

    add("SAS001", "ALL", len(claims), "row_count", "fact_claim", "row_count_absolute")
    add(
        "SAS002",
        "ALL",
        len({row["claim_key"] for row in claims}),
        "distinct_key_count",
        "fact_claim",
        "distinct_key_absolute",
    )
    add(
        "SAS003",
        "ALL",
        sum((row["total_allowed_amount"] for row in current_paid), Decimal("0")),
        "financial",
        "fact_claim",
        "financial_absolute",
    )
    add(
        "SAS004",
        "ALL",
        sum((row["net_paid_amount"] for row in current_paid), Decimal("0")),
        "financial",
        "fact_claim",
        "financial_absolute",
    )
    add(
        "SAS005",
        "ALL",
        sum(row["coverage_status"] == "active" for row in membership),
        "row_count",
        "fact_membership_month",
        "row_count_absolute",
    )
    for row in cost:
        scope = f"{row['service_month']}|{row['plan_key']}"
        add(
            "SAS006",
            scope,
            row["allowed_pmpm"],
            "rate",
            "monthly_cost_utilization",
            "rate_absolute",
        )
        add(
            "SAS007",
            scope,
            row["units_per_1000"],
            "rate",
            "monthly_cost_utilization",
            "rate_absolute",
        )
    for rule in sorted({row["rule_id"] for row in findings}):
        selected = [row for row in findings if row["rule_id"] == rule]
        add(
            "SAS008",
            rule,
            len(selected),
            "row_count",
            "rule_finding",
            "row_count_absolute",
        )
        add(
            "SAS009",
            rule,
            sum((row["amount_at_risk"] for row in selected), Decimal("0")),
            "financial",
            "rule_finding",
            "financial_absolute",
        )
    for group in sorted({row["treatment_group"] for row in panel}):
        add(
            "SAS010",
            group,
            sum(row["treatment_group"] == group for row in panel),
            "row_count",
            "provider_month_policy_panel",
            "row_count_absolute",
        )
    for row in effects:
        add(
            "SAS011",
            row["outcome_name"],
            row["coefficient"],
            "coefficient",
            "policy_effect_estimate",
            "coefficient_absolute",
        )
        add(
            "SAS012",
            row["outcome_name"],
            row["p_value"],
            "p_value",
            "policy_effect_estimate",
            "p_value_absolute",
        )
    return rows


def build_sas_package(
    contract_path: Path = DEFAULT_CONTRACT,
    trusted_root: Path = Path("data/curated/trusted_claims"),
    payment_root: Path = Path("data/curated/payment_integrity"),
    cost_root: Path = Path("data/curated/cost_intelligence"),
    policy_root: Path = Path("data/curated/policy_impact"),
    package_root: Path | None = None,
    evidence_path: Path | None = None,
    sample_path: Path = Path("data/sample/sas_reconciliation/reference_sample.csv"),
) -> dict[str, Any]:
    contract = load_yaml(contract_path)
    roots = {
        "trusted": trusted_root,
        "payment": payment_root,
        "cost": cost_root,
        "policy": policy_root,
    }
    package_root = package_root or Path("data/generated/sas_reconciliation")
    evidence_path = evidence_path or Path(contract["dataset"]["evidence_path"])
    tables = {}
    manifest = []
    for table, domain in INPUT_TABLES.items():
        source = roots[domain] / f"{table}.parquet"
        if not source.exists():
            raise FileNotFoundError(source)
        rows = pq.read_table(source).to_pylist()
        tables[table] = rows
        output = package_root / "input" / f"{table}.csv"
        _write_csv(rows, output)
        manifest.append(
            {
                "file_name": output.name,
                "row_count": len(rows),
                "sha256": _sha256(output),
            }
        )
    references = _reference_rows(tables, contract)
    reference_path = package_root / "reference" / "python_reference.csv"
    _write_csv(references, reference_path)
    _write_csv(references[:25], sample_path)
    manifest_path = package_root / "input_manifest.json"
    write_json_atomic({"files": manifest}, manifest_path)
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "execution_status": "not_executed",
        "sas_runtime_used": False,
        "input_file_count": len(manifest),
        "reference_row_count": len(references),
        "metric_ids": sorted({row["metric_id"] for row in references}),
        "input_manifest_sha256": _sha256(manifest_path),
        "reference_sha256": _sha256(reference_path),
        "checks": {
            "all_inputs_exported": len(manifest) == len(INPUT_TABLES),
            "all_inputs_hashed": all(row["sha256"] for row in manifest),
            "all_metrics_referenced": len({row["metric_id"] for row in references})
            == 12,
            "execution_not_fabricated": contract["runtime"]["execution_status"]
            == "not_executed",
        },
    }
    report["all_preparation_checks_passed"] = all(report["checks"].values())
    write_json_atomic(report, evidence_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build portable SAS reconciliation inputs and Python references."
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--trusted-root", type=Path, default=Path("data/curated/trusted_claims")
    )
    parser.add_argument(
        "--payment-root", type=Path, default=Path("data/curated/payment_integrity")
    )
    parser.add_argument(
        "--cost-root", type=Path, default=Path("data/curated/cost_intelligence")
    )
    parser.add_argument(
        "--policy-root", type=Path, default=Path("data/curated/policy_impact")
    )
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/sample/sas_reconciliation/reference_sample.csv"),
    )
    args = parser.parse_args()
    report = build_sas_package(
        args.contract,
        args.trusted_root,
        args.payment_root,
        args.cost_root,
        args.policy_root,
        args.package_root,
        args.evidence,
        args.sample,
    )
    print(f"SAS input files: {report['input_file_count']}")
    print(f"Python references: {report['reference_row_count']}")
    print(f"Execution status: {report['execution_status']}")


if __name__ == "__main__":
    main()
