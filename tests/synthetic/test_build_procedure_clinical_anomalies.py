from copy import deepcopy
from pathlib import Path

import yaml

from src.synthetic.build_procedure_clinical_anomalies import (
    build_procedure_clinical_anomalies,
)
from src.synthetic.build_synthetic_claims import build_synthetic_claims
from src.synthetic.build_synthetic_dimensions import build_synthetic_dimensions
from src.synthetic.build_synthetic_workflow import build_synthetic_workflow
from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]


def test_composed_procedure_clinical_stage_is_reproducible(tmp_path: Path) -> None:
    baseline_contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    baseline_contract["generation"]["members"] = 200
    baseline_contract["generation"]["providers"] = 80
    baseline_contract["generation"]["claim_headers"] = 2_000
    baseline_contract_path = tmp_path / "baseline_contract.yml"
    baseline_contract_path.write_text(
        yaml.safe_dump(baseline_contract, sort_keys=False), encoding="utf-8"
    )
    baseline_root = tmp_path / "baseline"
    baseline_report = tmp_path / "baseline_quality.json"
    build_synthetic_dimensions(
        contract_path=baseline_contract_path,
        output_root=baseline_root,
        sample_root=tmp_path / "dimension_samples",
        quality_report_path=tmp_path / "dimension_quality.json",
    )
    build_synthetic_claims(
        contract_path=baseline_contract_path,
        dimension_root=baseline_root,
        output_root=baseline_root,
        sample_root=tmp_path / "claim_samples",
        quality_report_path=tmp_path / "claim_quality.json",
    )
    build_synthetic_workflow(
        contract_path=baseline_contract_path,
        data_root=baseline_root,
        sample_root=tmp_path / "workflow_samples",
        quality_report_path=baseline_report,
    )
    anomaly_contract = deepcopy(
        load_yaml(ROOT / "config/anomaly_injection_contract.yml")
    )
    anomaly_contract["dataset"]["baseline_quality_report"] = str(baseline_report)
    anomaly_contract_path = tmp_path / "anomaly_contract.yml"
    anomaly_contract_path.write_text(
        yaml.safe_dump(anomaly_contract, sort_keys=False), encoding="utf-8"
    )
    output_root = tmp_path / "anomalous"
    arguments = {
        "baseline_contract_path": baseline_contract_path,
        "anomaly_contract_path": anomaly_contract_path,
        "baseline_root": baseline_root,
        "output_root": output_root,
        "sample_root": tmp_path / "samples",
        "quality_report_path": tmp_path / "procedure_quality.json",
    }
    first = build_procedure_clinical_anomalies(**arguments)
    output_names = (
        "claim_header",
        "claim_line",
        "payment_transaction",
        "anomaly_injection",
        "anomaly_field_change",
        "baseline_hash_manifest",
    )
    first_bytes = {
        name: (output_root / f"{name}.parquet").read_bytes() for name in output_names
    }
    repeated = build_procedure_clinical_anomalies(**arguments)

    assert first["all_checks_passed"] is True
    assert repeated["all_checks_passed"] is True
    assert first["injection_count"] == 500
    assert first["ground_truth"] == repeated["ground_truth"]
    assert first["changed_tables"] == repeated["changed_tables"]
    assert first_bytes == {
        name: (output_root / f"{name}.parquet").read_bytes() for name in output_names
    }
