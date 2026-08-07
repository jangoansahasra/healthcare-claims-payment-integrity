from __future__ import annotations

import argparse
import csv
import hashlib
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

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


def validate_sas_execution(
    log_path: Path,
    result_path: Path,
    contract_path: Path = DEFAULT_CONTRACT,
    package_root: Path = Path("data/generated/sas_reconciliation"),
    evidence_path: Path | None = None,
    execution_timezone: str = "America/New_York",
) -> dict[str, Any]:
    """Validate real SAS artifacts and publish checksum-backed execution evidence."""
    contract = load_yaml(contract_path)
    evidence_path = evidence_path or Path(contract["dataset"]["evidence_path"])
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    log_scan = scan_sas_log(log_text, contract)

    with result_path.open(encoding="utf-8", newline="") as stream:
        results = list(csv.DictReader(stream))
    reference_path = package_root / "reference" / "python_reference.csv"
    with reference_path.open(encoding="utf-8", newline="") as stream:
        references = list(csv.DictReader(stream))

    def note(name: str) -> str | None:
        matches = re.findall(rf"^NOTE: M08_{name}=(.+)$", log_text, re.MULTILINE)
        return matches[-1].strip() if matches else None

    execution_id = note("EXECUTION_ID")
    sas_version = note("SAS_VERSION")
    platform = note("PLATFORM")
    started_text = note("EXECUTED_AT")
    modified = re.findall(
        r"Last Modified=(\d{2}[A-Za-z]{3}\d{4}:\d{2}:\d{2}:\d{2})", log_text
    )
    timezone = ZoneInfo(execution_timezone)
    started = (
        datetime.fromisoformat(started_text).replace(tzinfo=timezone)
        if started_text
        else None
    )
    completed = (
        datetime.strptime(modified[-1], "%d%b%Y:%H:%M:%S").replace(tzinfo=timezone)
        if modified
        else None
    )

    required_columns = set(contract["result_schema"]["columns"])
    actual_columns = set(results[0]) if results else set()
    result_keys = {(row["metric_id"], row["comparison_scope"]) for row in results}
    reference_keys = {(row["metric_id"], row["comparison_scope"]) for row in references}
    execution_ids = {row.get("execution_id", "") for row in results}
    missing_sas_values = sum(not row.get("sas_value", "").strip() for row in results)
    failed_comparisons = sum(
        row.get("passed", "").strip() not in {"1", "1.0"} for row in results
    )
    version_match = re.search(r"M(\d+)", sas_version or "")
    version_accepted = bool(version_match and int(version_match.group(1)) >= 7)
    checks = {
        "real_sas_log_passed": log_scan["passed"],
        "runtime_version_accepted": version_accepted,
        "runtime_platform_recorded": bool(platform),
        "execution_times_recorded": bool(
            started and completed and completed >= started
        ),
        "result_schema_conforms": required_columns <= actual_columns,
        "execution_id_consistent": execution_ids == {execution_id}
        and bool(execution_id),
        "reference_keys_match": result_keys == reference_keys,
        "all_reference_rows_returned": len(results) == len(references),
        "all_comparisons_passed": failed_comparisons == 0,
        "no_missing_sas_values": missing_sas_values == 0,
    }
    program_checksums = {
        row["path"]: _sha256(Path(row["path"])) for row in contract["program_order"]
    }
    report = {
        "report_version": 2,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "execution_status": "passed" if all(checks.values()) else "failed",
        "sas_runtime_used": True,
        "execution_id": execution_id,
        "sas_product_name": "Base SAS",
        "sas_version": sas_version,
        "execution_environment": platform,
        "execution_timezone": execution_timezone,
        "execution_started_at_utc": started.astimezone(UTC).isoformat()
        if started
        else None,
        "execution_completed_at_utc": completed.astimezone(UTC).isoformat()
        if completed
        else None,
        "input_file_count": len(INPUT_TABLES),
        "reference_row_count": len(references),
        "result_row_count": len(results),
        "passed_comparison_count": len(results) - failed_comparisons,
        "failed_comparison_count": failed_comparisons,
        "missing_sas_value_count": missing_sas_values,
        "metric_ids": sorted({row["metric_id"] for row in results}),
        "input_manifest_sha256": _sha256(package_root / "input_manifest.json"),
        "reference_sha256": _sha256(reference_path),
        "sas_log_sha256": _sha256(log_path),
        "sas_result_sha256": _sha256(result_path),
        "program_checksums": program_checksums,
        "log_scan": log_scan,
        "checks": checks,
    }
    report["all_execution_checks_passed"] = all(checks.values())
    write_json_atomic(report, evidence_path)
    return report


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
            "execution_not_fabricated": contract["runtime"][
                "package_preparation_status"
            ]
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
    parser.add_argument("--validate-log", type=Path)
    parser.add_argument("--validate-result", type=Path)
    parser.add_argument("--execution-timezone", default="America/New_York")
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/sample/sas_reconciliation/reference_sample.csv"),
    )
    args = parser.parse_args()
    if args.validate_log or args.validate_result:
        if not args.validate_log or not args.validate_result:
            parser.error(
                "--validate-log and --validate-result must be provided together"
            )
        report = validate_sas_execution(
            args.validate_log,
            args.validate_result,
            args.contract,
            args.package_root or Path("data/generated/sas_reconciliation"),
            args.evidence,
            args.execution_timezone,
        )
        print(f"Execution status: {report['execution_status']}")
        print(f"SAS comparisons passed: {report['passed_comparison_count']}")
        return
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
