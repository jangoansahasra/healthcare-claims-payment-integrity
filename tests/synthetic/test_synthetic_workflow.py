from copy import deepcopy
from pathlib import Path

from src.synthetic.synthetic_claims import generate_claim_rows
from src.synthetic.synthetic_dimensions import generate_dimension_rows, load_yaml
from src.synthetic.synthetic_workflow import (
    generate_workflow_rows,
    validate_workflow_rows,
)

ROOT = Path(__file__).resolve().parents[2]


def small_inputs() -> tuple[dict, dict, list[dict]]:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 80
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
    configuration = load_yaml(ROOT / "config/synthetic_workflow_generation.yml")
    return contract, configuration, claims["claim_header"]


def test_clean_workflow_is_deterministic_and_valid() -> None:
    contract, configuration, headers = small_inputs()
    first = generate_workflow_rows(contract, configuration, headers)
    second = generate_workflow_rows(contract, configuration, headers)

    assert first == second
    assert first["claim_review"]
    assert len(first["claim_review"]) == len(first["audit_outcome"])
    assert first["recovery_transaction"] == []
    assert all(validate_workflow_rows(first, headers, contract).values())


def test_clean_audits_have_no_confirmed_findings() -> None:
    contract, configuration, headers = small_inputs()
    rows = generate_workflow_rows(contract, configuration, headers)

    assert {row["outcome"] for row in rows["audit_outcome"]} <= {
        "no_issue",
        "inconclusive",
    }
    assert all(row["confirmed_amount"] == 0 for row in rows["audit_outcome"])
