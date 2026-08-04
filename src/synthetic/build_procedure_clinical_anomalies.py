from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from src.synthetic.build_ledger_temporal_anomalies import GROUND_TRUTH_TABLES, read_rows
from src.synthetic.build_provider_pattern_anomalies import (
    build_provider_pattern_anomalies,
)
from src.synthetic.build_record_level_anomalies import (
    DEFAULT_ANOMALY_CONTRACT_PATH,
    DEFAULT_BASELINE_CONTRACT_PATH,
    contract_table_schema,
)
from src.synthetic.build_synthetic_dimensions import (
    file_sha256,
    write_json_atomic,
    write_parquet_atomic,
    write_sample_csv,
)
from src.synthetic.procedure_clinical_anomalies import (
    PROCEDURE_CLINICAL_CHANGED_TABLES,
    PROCEDURE_CLINICAL_RULES,
    inject_procedure_clinical_anomalies,
    validate_procedure_clinical_anomalies,
)
from src.synthetic.record_level_anomalies import SyntheticAnomalyError
from src.synthetic.synthetic_dimensions import content_hash, load_yaml, table_schema

DEFAULT_QUALITY_REPORT_PATH = Path(
    "data/metadata/quality/procedure_clinical_anomaly_injection.json"
)


def build_procedure_clinical_anomalies(
    baseline_contract_path: Path = DEFAULT_BASELINE_CONTRACT_PATH,
    anomaly_contract_path: Path = DEFAULT_ANOMALY_CONTRACT_PATH,
    baseline_root: Path | None = None,
    output_root: Path | None = None,
    sample_root: Path | None = None,
    quality_report_path: Path = DEFAULT_QUALITY_REPORT_PATH,
) -> dict[str, Any]:
    """Rebuild PI001-PI008 and append deterministic PI009 and PI010."""
    baseline_contract = load_yaml(baseline_contract_path)
    anomaly_contract = load_yaml(anomaly_contract_path)
    dataset = anomaly_contract["dataset"]
    baseline_root = baseline_root or Path(dataset["clean_baseline_root"])
    output_root = output_root or Path(dataset["anomalous_output_root"])
    sample_root = sample_root or Path(dataset["publishable_sample_root"])
    build_provider_pattern_anomalies(
        baseline_contract_path=baseline_contract_path,
        anomaly_contract_path=anomaly_contract_path,
        baseline_root=baseline_root,
        output_root=output_root,
        sample_root=sample_root,
        quality_report_path=output_root / "_provider_stage_quality.json",
    )
    table_names = list(baseline_contract["tables"])
    before_stage = read_rows(output_root, table_names)
    ground_truth = read_rows(output_root, GROUND_TRUTH_TABLES)
    baseline_hashes = {
        name: file_sha256(baseline_root / f"{name}.parquet") for name in table_names
    }
    extended, injections, changes = inject_procedure_clinical_anomalies(
        before_stage,
        ground_truth["anomaly_injection"],
        ground_truth["anomaly_field_change"],
        anomaly_contract,
    )
    for name in PROCEDURE_CLINICAL_CHANGED_TABLES:
        write_parquet_atomic(
            extended[name],
            table_schema(baseline_contract, name),
            output_root / f"{name}.parquet",
        )
    combined_ground_truth = {
        "anomaly_injection": injections,
        "anomaly_field_change": changes,
        "baseline_hash_manifest": ground_truth["baseline_hash_manifest"],
    }
    checks = validate_procedure_clinical_anomalies(
        before_stage, extended, injections, changes, anomaly_contract
    )
    for name, rows in combined_ground_truth.items():
        schema = contract_table_schema(anomaly_contract, name)
        write_parquet_atomic(rows, schema, output_root / f"{name}.parquet")
        checks[f"{name}_schema"] = pq.read_schema(
            output_root / f"{name}.parquet"
        ).equals(schema)
        checks[f"{name}_rows"] = pq.read_metadata(
            output_root / f"{name}.parquet"
        ).num_rows == len(rows)
    new_injections = [
        row for row in injections if row["rule_id"] in PROCEDURE_CLINICAL_RULES
    ]
    new_ids = {row["injection_id"] for row in new_injections}
    new_changes = [row for row in changes if row["injection_id"] in new_ids]
    write_sample_csv(
        new_injections,
        contract_table_schema(anomaly_contract, "anomaly_injection").names,
        sample_root / "procedure_clinical_anomaly_injection_sample.csv",
    )
    write_sample_csv(
        new_changes,
        contract_table_schema(anomaly_contract, "anomaly_field_change").names,
        sample_root / "procedure_clinical_field_change_sample.csv",
    )
    checks["baseline_unchanged"] = all(
        file_sha256(baseline_root / f"{name}.parquet") == baseline_hashes[name]
        for name in table_names
    )
    rule_counts = {
        rule_id: sum(row["rule_id"] == rule_id for row in injections)
        for rule_id in (f"PI{index:03d}" for index in range(1, 11))
    }
    rule_exposure = {
        rule_id: format(
            sum(
                (
                    row["expected_financial_exposure"]
                    for row in injections
                    if row["rule_id"] == rule_id
                ),
                start=Decimal("0.00"),
            ),
            "f",
        )
        for rule_id in rule_counts
    }
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "baseline_contract_version": baseline_contract["contract_version"],
        "anomaly_contract_version": anomaly_contract["contract_version"],
        "deterministic_seed": dataset["deterministic_seed"],
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
            for name, rows in combined_ground_truth.items()
        },
        "changed_tables": {
            name: {
                "row_count": len(extended[name]),
                "content_sha256": content_hash(
                    extended[name], table_schema(baseline_contract, name).names
                ),
            }
            for name in PROCEDURE_CLINICAL_CHANGED_TABLES
        },
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SyntheticAnomalyError(
            "Procedure-clinical anomaly checks failed: " + ", ".join(failed)
        )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject deterministic procedure and clinical anomalies."
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
    report = build_procedure_clinical_anomalies(
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
