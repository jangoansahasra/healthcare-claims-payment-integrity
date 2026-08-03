from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from src.synthetic.synthetic_claims import (
    decimal_between,
    generate_claim_rows,
    validate_claim_rows,
)
from src.synthetic.synthetic_dimensions import generate_dimension_rows, load_yaml

ROOT = Path(__file__).resolve().parents[2]


def small_inputs() -> tuple[dict, dict, dict]:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    dimensions_config = load_yaml(ROOT / "config/synthetic_dimension_generation.yml")
    claim_config = deepcopy(load_yaml(ROOT / "config/synthetic_claim_generation.yml"))
    contract["generation"]["members"] = 80
    contract["generation"]["providers"] = 40
    contract["generation"]["claim_headers"] = 500
    dimensions = generate_dimension_rows(contract, dimensions_config)
    return contract, claim_config, dimensions


def test_decimal_between_is_stable_and_fixed_scale() -> None:
    value = decimal_between(7, "amount", 1, 10, 20, Decimal("0.01"))

    assert value == decimal_between(7, "amount", 1, 10, 20, Decimal("0.01"))
    assert Decimal("10.00") <= value <= Decimal("20.00")
    assert value.as_tuple().exponent == -2


def test_clean_claim_generation_satisfies_quality_rules() -> None:
    contract, configuration, dimensions = small_inputs()
    rows = generate_claim_rows(contract, configuration, dimensions)
    checks = validate_claim_rows(rows, contract, dimensions)

    assert len(rows["claim_header"]) == 500
    assert len(rows["adjudication_event"]) == 1000
    assert set(row["claim_type"] for row in rows["claim_header"]) == {
        "professional",
        "inpatient",
        "outpatient",
        "pharmacy",
    }
    assert all(checks.values())


def test_claim_generation_is_reproducible() -> None:
    contract, configuration, dimensions = small_inputs()

    assert generate_claim_rows(
        contract, configuration, dimensions
    ) == generate_claim_rows(contract, configuration, dimensions)


def test_denied_claims_have_zero_adjudicated_amounts_and_no_payment() -> None:
    contract, configuration, dimensions = small_inputs()
    rows = generate_claim_rows(contract, configuration, dimensions)
    denied = {
        row["claim_id"]
        for row in rows["claim_header"]
        if row["claim_status"] == "denied"
    }
    paid = {row["claim_id"] for row in rows["payment_transaction"]}

    assert denied
    assert denied.isdisjoint(paid)
    assert all(
        row["allowed_amount"] == 0 and row["member_liability_amount"] == 0
        for row in rows["claim_line"]
        if row["claim_id"] in denied
    )
