from copy import deepcopy
from pathlib import Path

from src.synthetic.ledger_temporal_anomalies import inject_ledger_temporal_anomalies
from src.synthetic.provider_pattern_anomalies import (
    inject_provider_pattern_anomalies,
    validate_provider_pattern_anomalies,
)
from src.synthetic.record_level_anomalies import inject_record_level_anomalies
from src.synthetic.synthetic_claims import generate_claim_rows
from src.synthetic.synthetic_dimensions import generate_dimension_rows, load_yaml
from src.synthetic.synthetic_workflow import generate_workflow_rows

ROOT = Path(__file__).resolve().parents[2]


def ledger_stage() -> tuple[dict, list[dict], list[dict], dict]:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 200
    contract["generation"]["providers"] = 80
    contract["generation"]["claim_headers"] = 2_000
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
    anomaly_contract = deepcopy(
        load_yaml(ROOT / "config/anomaly_injection_contract.yml")
    )
    anomaly_contract["scenario_defaults"]["target_count"] = 10
    baseline = {**dimensions, **claims, **workflow}
    record_stage, injections, changes = inject_record_level_anomalies(
        baseline, anomaly_contract
    )
    ledger, injections, changes = inject_ledger_temporal_anomalies(
        record_stage, injections, changes, anomaly_contract
    )
    return ledger, injections, changes, anomaly_contract


def test_provider_pattern_injections_are_deterministic_and_valid() -> None:
    stage, injections, changes, contract = ledger_stage()
    original = deepcopy(stage)
    first = inject_provider_pattern_anomalies(stage, injections, changes, contract)
    second = inject_provider_pattern_anomalies(stage, injections, changes, contract)
    extended, combined_injections, combined_changes = first

    assert first == second
    assert stage == original
    assert len(combined_injections) == 80
    assert all(
        validate_provider_pattern_anomalies(
            stage,
            extended,
            combined_injections,
            combined_changes,
            contract,
        ).values()
    )


def test_pi007_and_pi008_have_positive_reconciled_exposure() -> None:
    stage, injections, changes, contract = ledger_stage()
    _, combined, _ = inject_provider_pattern_anomalies(
        stage, injections, changes, contract
    )

    assert all(
        row["expected_financial_exposure"] > 0
        for row in combined
        if row["rule_id"] in {"PI007", "PI008"}
    )
    assert {row["rule_id"] for row in combined} == {
        f"PI{index:03d}" for index in range(1, 9)
    }
