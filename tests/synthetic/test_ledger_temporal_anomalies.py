from copy import deepcopy
from pathlib import Path

from src.synthetic.ledger_temporal_anomalies import (
    inject_ledger_temporal_anomalies,
    validate_ledger_temporal_anomalies,
)
from src.synthetic.record_level_anomalies import inject_record_level_anomalies
from src.synthetic.synthetic_claims import generate_claim_rows
from src.synthetic.synthetic_dimensions import generate_dimension_rows, load_yaml
from src.synthetic.synthetic_workflow import generate_workflow_rows

ROOT = Path(__file__).resolve().parents[2]


def record_level_stage() -> tuple[dict, list[dict], list[dict], dict]:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 100
    contract["generation"]["providers"] = 40
    contract["generation"]["claim_headers"] = 500
    dimensions = generate_dimension_rows(
        contract, load_yaml(ROOT / "config/synthetic_dimension_generation.yml")
    )
    claims = generate_claim_rows(
        contract,
        load_yaml(ROOT / "config/synthetic_claim_generation.yml"),
        dimensions,
    )
    workflow = generate_workflow_rows(
        contract,
        load_yaml(ROOT / "config/synthetic_workflow_generation.yml"),
        claims["claim_header"],
    )
    anomaly_contract = load_yaml(ROOT / "config/anomaly_injection_contract.yml")
    stage, injections, changes = inject_record_level_anomalies(
        {**dimensions, **claims, **workflow}, anomaly_contract
    )
    return stage, injections, changes, anomaly_contract


def test_ledger_temporal_injections_are_deterministic_and_valid() -> None:
    stage, injections, changes, contract = record_level_stage()
    original = deepcopy(stage)
    first = inject_ledger_temporal_anomalies(stage, injections, changes, contract)
    second = inject_ledger_temporal_anomalies(stage, injections, changes, contract)
    extended, combined_injections, combined_changes = first

    assert first == second
    assert stage == original
    assert len(combined_injections) == 300
    assert all(
        validate_ledger_temporal_anomalies(
            stage,
            extended,
            combined_injections,
            combined_changes,
            target_count=50,
        ).values()
    )


def test_pi003_has_positive_exposure_and_pi004_has_zero_exposure() -> None:
    stage, injections, changes, contract = record_level_stage()
    _, combined, _ = inject_ledger_temporal_anomalies(
        stage, injections, changes, contract
    )

    assert all(
        row["expected_financial_exposure"] > 0
        for row in combined
        if row["rule_id"] == "PI003"
    )
    assert all(
        row["expected_financial_exposure"] == 0
        for row in combined
        if row["rule_id"] == "PI004"
    )
