from copy import deepcopy
from pathlib import Path

from src.synthetic.record_level_anomalies import (
    inject_record_level_anomalies,
    validate_record_level_anomalies,
)
from src.synthetic.synthetic_claims import generate_claim_rows
from src.synthetic.synthetic_dimensions import generate_dimension_rows, load_yaml
from src.synthetic.synthetic_workflow import generate_workflow_rows

ROOT = Path(__file__).resolve().parents[2]


def small_baseline() -> tuple[dict, dict]:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 100
    contract["generation"]["providers"] = 40
    contract["generation"]["claim_headers"] = 500
    dimensions = generate_dimension_rows(
        contract,
        load_yaml(ROOT / "config/synthetic_dimension_generation.yml"),
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
    return {**dimensions, **claims, **workflow}, load_yaml(
        ROOT / "config/anomaly_injection_contract.yml"
    )


def test_record_level_injections_are_deterministic_and_isolated() -> None:
    baseline, anomaly_contract = small_baseline()
    original = deepcopy(baseline)
    first = inject_record_level_anomalies(baseline, anomaly_contract)
    second = inject_record_level_anomalies(baseline, anomaly_contract)
    anomalous, injections, changes = first

    assert first == second
    assert baseline == original
    assert len(injections) == 200
    assert {row["rule_id"] for row in injections} == {
        "PI001",
        "PI002",
        "PI005",
        "PI006",
    }
    assert all(
        validate_record_level_anomalies(
            baseline, anomalous, injections, changes, target_count=50
        ).values()
    )


def test_ground_truth_has_complete_positive_exposure_and_lineage() -> None:
    baseline, anomaly_contract = small_baseline()
    _, injections, changes = inject_record_level_anomalies(baseline, anomaly_contract)

    assert all(row["expected_financial_exposure"] > 0 for row in injections)
    assert {row["injection_id"] for row in injections} == {
        row["injection_id"] for row in changes
    }
    assert all(row["overlap_group"] is None for row in injections)
    assert all(row["synthetic_record"] is True for row in injections)
