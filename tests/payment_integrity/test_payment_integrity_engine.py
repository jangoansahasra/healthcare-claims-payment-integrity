from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.payment_integrity.payment_integrity_engine import (
    PaymentIntegrityError,
    execute_rules,
)
from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]


def read_detection_inputs() -> dict:
    root = ROOT / "data/curated/trusted_claims"
    names = (
        "dim_provider",
        "dim_date",
        "dim_service",
        "fact_claim",
        "fact_claim_line",
        "fact_payment_transaction",
    )
    return {name: pq.read_table(root / f"{name}.parquet").to_pylist() for name in names}


def test_detection_rejects_ground_truth_input() -> None:
    trusted = read_detection_inputs()
    trusted["bridge_claim_anomaly"] = []

    with pytest.raises(PaymentIntegrityError, match="must not contain ground truth"):
        execute_rules(
            trusted,
            load_yaml(ROOT / "config/payment_integrity_contract.yml"),
            load_yaml(ROOT / "config/payment_integrity_rules.yml"),
            load_yaml(ROOT / "config/anomaly_injection_contract.yml"),
        )


def test_all_rules_produce_explainable_capped_findings() -> None:
    findings, evidence, eligible = execute_rules(
        read_detection_inputs(),
        load_yaml(ROOT / "config/payment_integrity_contract.yml"),
        load_yaml(ROOT / "config/payment_integrity_rules.yml"),
        load_yaml(ROOT / "config/anomaly_injection_contract.yml"),
    )

    assert len(findings) == 500
    assert {row["rule_id"] for row in findings} == {
        f"PI{number:03d}" for number in range(1, 11)
    }
    assert all(row["explanation"] for row in findings)
    assert all(row["amount_at_risk"] >= 0 for row in findings)
    assert {row["finding_id"] for row in findings} == {
        row["finding_id"] for row in evidence
    }
    assert all(count > 0 for count in eligible.values())
