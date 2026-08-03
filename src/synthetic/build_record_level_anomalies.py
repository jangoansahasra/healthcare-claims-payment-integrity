from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import (
    file_sha256,
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.record_level_anomalies import (
    CHANGED_TABLES,
    RECORD_LEVEL_RULES,
    SyntheticAnomalyError,
    inject_record_level_anomalies,
    validate_record_level_anomalies,
)
from src.synthetic.synthetic_dimensions import (
    arrow_type,
    content_hash,
    load_yaml,
    table_schema,
)

DEFAULT_BASELINE_CONTRACT_PATH = Path("config/synthetic_data_contract.yml")
DEFAULT_ANOMALY_CONTRACT_PATH = Path("config/anomaly_injection_contract.yml")
DEFAULT_QUALITY_REPORT_PATH = Path(
    "data/metadata/quality/record_level_anomaly_injection.json"
)


def contract_table_schema(contract: dict[str, Any], table_name: str) -> pa.Schema:
    """Build an Arrow schema from the anomaly ground-truth contract."""
    columns = contract["tables"][table_name]["columns"]
    return pa.schema(
        [
            pa.field(name, arrow_type(details["type"]), nullable=details["nullable"])
            for name, details in columns.items()
        ]
    )


def schema_sha256(schema: pa.Schema) -> str:
    """Hash a stable Arrow schema representation."""
    return hashlib.sha256(schema.to_string().encode()).hexdigest()


def read_baseline(
    root: Path, table_names: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Read all required clean baseline tables."""
    missing = [name for name in table_names if not (root / f"{name}.parquet").is_file()]
    if missing:
        raise SyntheticAnomalyError(
            "Missing clean baseline tables: " + ", ".join(missing)
        )
    return {
        name: pq.read_table(root / f"{name}.parquet").to_pylist()
        for name in table_names
    }


def clone_parquet_tables(
    source_root: Path, output_root: Path, names: list[str]
) -> None:
    """Clone baseline Parquet bytes atomically into the anomalous output root."""
    output_root.mkdir(parents=True, exist_ok=True)
    for name in names:
        source = source_root / f"{name}.parquet"
        target = output_root / f"{name}.parquet"
        partial = target.with_suffix(".parquet.partial")
        partial.unlink(missing_ok=True)
        try:
            shutil.copyfile(source, partial)
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)


def build_record_level_anomalies(
    baseline_contract_path: Path = DEFAULT_BASELINE_CONTRACT_PATH,
    anomaly_contract_path: Path = DEFAULT_ANOMALY_CONTRACT_PATH,
    baseline_root: Path | None = None,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path = DEFAULT_QUALITY_REPORT_PATH,
) -> dict[str, Any]:
    """Clone M02 and inject deterministic PI001, PI002, PI005, and PI006."""
    baseline_contract = load_yaml(baseline_contract_path)
    anomaly_contract = load_yaml(anomaly_contract_path)
    dataset = anomaly_contract["dataset"]
    baseline_root = baseline_root or Path(dataset["clean_baseline_root"])
    output_root = output_root or Path(dataset["anomalous_output_root"])
    sample_root = sample_root or Path(dataset["publishable_sample_root"])
    table_names = list(baseline_contract["tables"])
    baseline_report_path = Path(dataset["baseline_quality_report"])
    baseline_report = json.loads(baseline_report_path.read_text(encoding="utf-8"))
    baseline = read_baseline(baseline_root, table_names)
    baseline_file_hashes = {
        name: file_sha256(baseline_root / f"{name}.parquet") for name in table_names
    }
    checks = {
        "baseline_report_passed": baseline_report["all_checks_passed"] is True,
        "baseline_table_count": len(table_names) == 14,
        "baseline_content_hashes": all(
            content_hash(baseline[name], table_schema(baseline_contract, name).names)
            == baseline_report["tables"][name]["content_sha256"]
            for name in table_names
        ),
    }
    clone_parquet_tables(baseline_root, output_root, table_names)
    checks["initial_clone_byte_identity"] = all(
        file_sha256(output_root / f"{name}.parquet") == baseline_file_hashes[name]
        for name in table_names
    )

    anomalous, injections, changes = inject_record_level_anomalies(
        baseline, anomaly_contract
    )
    for name in CHANGED_TABLES:
        write_parquet_atomic(
            anomalous[name],
            table_schema(baseline_contract, name),
            output_root / f"{name}.parquet",
        )

    manifest = []
    for name in table_names:
        schema = table_schema(baseline_contract, name)
        manifest.append(
            {
                "table_name": name,
                "row_count": len(baseline[name]),
                "content_sha256": baseline_report["tables"][name]["content_sha256"],
                "schema_sha256": schema_sha256(schema),
                "baseline_contract_version": baseline_contract["contract_version"],
            }
        )
    ground_truth = {
        "anomaly_injection": injections,
        "anomaly_field_change": changes,
        "baseline_hash_manifest": manifest,
    }
    for name, rows in ground_truth.items():
        schema = contract_table_schema(anomaly_contract, name)
        write_parquet_atomic(rows, schema, output_root / f"{name}.parquet")
        write_sample_csv(rows, schema.names, sample_root / f"{name}_sample.csv")
        checks[f"{name}_schema"] = pq.read_schema(
            output_root / f"{name}.parquet"
        ).equals(schema)
        checks[f"{name}_rows"] = pq.read_metadata(
            output_root / f"{name}.parquet"
        ).num_rows == len(rows)

    checks.update(
        validate_record_level_anomalies(
            baseline,
            anomalous,
            injections,
            changes,
            int(anomaly_contract["scenario_defaults"]["target_count"]),
        )
    )
    checks["unchanged_clone_bytes"] = all(
        file_sha256(output_root / f"{name}.parquet") == baseline_file_hashes[name]
        for name in set(table_names) - set(CHANGED_TABLES)
    )
    checks["baseline_unchanged_after_injection"] = all(
        file_sha256(baseline_root / f"{name}.parquet") == baseline_file_hashes[name]
        for name in table_names
    )
    rule_counts = {
        rule_id: sum(row["rule_id"] == rule_id for row in injections)
        for rule_id in RECORD_LEVEL_RULES
    }
    rule_exposure = {
        rule_id: format(
            sum(
                (
                    row["expected_financial_exposure"]
                    for row in injections
                    if row["rule_id"] == rule_id
                ),
                start=0,
            ),
            "f",
        )
        for rule_id in RECORD_LEVEL_RULES
    }
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "baseline_contract_version": baseline_contract["contract_version"],
        "anomaly_contract_version": anomaly_contract["contract_version"],
        "deterministic_seed": dataset["deterministic_seed"],
        "baseline_contract_sha256": file_sha256(baseline_contract_path),
        "anomaly_contract_sha256": file_sha256(anomaly_contract_path),
        "baseline_table_count": len(table_names),
        "injection_count": len(injections),
        "field_change_count": len(changes),
        "rule_counts": rule_counts,
        "rule_expected_financial_exposure": rule_exposure,
        "ground_truth": {
            name: {
                "row_count": len(rows),
                "content_sha256": content_hash(
                    rows, contract_table_schema(anomaly_contract, name).names
                ),
            }
            for name, rows in ground_truth.items()
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SyntheticAnomalyError(
            "Record-level anomaly quality checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject deterministic record-level payment-integrity anomalies."
    )
    parser.add_argument(
        "--baseline-contract", type=Path, default=DEFAULT_BASELINE_CONTRACT_PATH
    )
    parser.add_argument(
        "--anomaly-contract", type=Path, default=DEFAULT_ANOMALY_CONTRACT_PATH
    )
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--sample-root", type=Path)
    parser.add_argument(
        "--quality-report", type=Path, default=DEFAULT_QUALITY_REPORT_PATH
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_record_level_anomalies(
        args.baseline_contract,
        args.anomaly_contract,
        args.baseline_root,
        args.output_root,
        args.sample_root,
        args.quality_report,
    )
    print(f"Injected anomalies: {report['injection_count']}")
    print(f"Field changes: {report['field_change_count']}")
    print(f"Rule counts: {report['rule_counts']}")
    print(f"All quality checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
