from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.synthetic.build_record_level_anomalies import contract_table_schema
from src.synthetic.build_synthetic_dimensions import write_parquet_atomic
from src.synthetic.synthetic_dimensions import load_yaml, table_schema
from src.transformation.build_trusted_claims import build_trusted_claims
from src.transformation.trusted_claims import (
    generate_trusted_rows,
    validate_trusted_rows,
)

ROOT = Path(__file__).resolve().parents[2]


def source_fixture() -> dict[str, list[dict]]:
    first = date(2025, 1, 15)
    second = date(2025, 2, 15)
    return {
        "member": [
            {
                "member_id": "MBR00000001",
                "birth_year": 1980,
                "sex_code": "F",
                "state_code": "NY",
                "synthetic_record": True,
            }
        ],
        "provider": [
            {
                "provider_id": "PRV000001",
                "provider_entity_type": "individual",
                "specialty_group": "primary_care",
                "state_code": "NY",
                "calibration_source_id": "synthetic_fixture",
                "calibration_version": "1",
                "synthetic_record": True,
            }
        ],
        "plan": [
            {
                "plan_id": "PLN0001",
                "plan_type": "commercial",
                "product_line": "individual",
                "effective_date": date(2025, 1, 1),
                "termination_date": None,
            }
        ],
        "membership_month": [
            {
                "member_id": "MBR00000001",
                "plan_id": "PLN0001",
                "coverage_month": value.replace(day=1),
                "coverage_start_date": value.replace(day=1),
                "coverage_end_date": date(value.year, value.month, 28),
                "coverage_status": "active",
            }
            for value in (first, second)
        ],
        "claim_header": [
            {
                "claim_id": "CLM0000000001V01",
                "logical_claim_id": "LCL0000000001",
                "claim_version_number": 1,
                "prior_claim_id": None,
                "member_id": "MBR00000001",
                "plan_id": "PLN0001",
                "billing_provider_id": "PRV000001",
                "rendering_provider_id": "PRV000001",
                "claim_type": "professional",
                "claim_status": "paid",
                "service_from_date": first,
                "service_through_date": first,
                "received_date": date(2025, 1, 16),
                "adjudication_date": date(2025, 1, 17),
                "principal_diagnosis_code": "I10",
                "total_charge_amount": Decimal("100.00"),
                "total_allowed_amount": Decimal("80.00"),
                "total_member_liability_amount": Decimal("10.00"),
            },
            {
                "claim_id": "CLM0000000001V02",
                "logical_claim_id": "LCL0000000001",
                "claim_version_number": 2,
                "prior_claim_id": "CLM0000000001V01",
                "member_id": "MBR00000001",
                "plan_id": "PLN0001",
                "billing_provider_id": "PRV000001",
                "rendering_provider_id": "PRV000001",
                "claim_type": "professional",
                "claim_status": "adjusted",
                "service_from_date": second,
                "service_through_date": second,
                "received_date": date(2025, 2, 16),
                "adjudication_date": date(2025, 2, 17),
                "principal_diagnosis_code": "M1711",
                "total_charge_amount": Decimal("120.00"),
                "total_allowed_amount": Decimal("90.00"),
                "total_member_liability_amount": Decimal("10.00"),
            },
        ],
        "claim_line": [
            {
                "claim_line_id": f"LIN{index:012d}",
                "claim_id": f"CLM0000000001V0{index}",
                "line_number": 1,
                "rendering_provider_id": "PRV000001",
                "service_code_system": "HCPCS",
                "service_code": "99213" if index == 1 else "97110",
                "service_date": first if index == 1 else second,
                "place_of_service_code": "11",
                "units": Decimal("1.0000"),
                "charge_amount": Decimal("100.00") if index == 1 else Decimal("120.00"),
                "allowed_amount": Decimal("80.00") if index == 1 else Decimal("90.00"),
                "member_liability_amount": Decimal("10.00"),
            }
            for index in (1, 2)
        ],
        "payment_transaction": [
            {
                "payment_transaction_id": f"PAY{index:012d}",
                "claim_id": f"CLM0000000001V0{index}",
                "transaction_sequence_number": 1,
                "transaction_date": date(2025, index, 18),
                "transaction_type": "payment",
                "signed_transaction_amount": Decimal("70.00")
                if index == 1
                else Decimal("80.00"),
                "reverses_transaction_id": None,
            }
            for index in (1, 2)
        ],
        "claim_review": [
            {
                "review_id": "REV0000000001",
                "claim_id": "CLM0000000001V02",
                "review_status": "completed",
                "selected_date": date(2025, 2, 19),
                "completed_date": date(2025, 2, 20),
                "selection_reason": "fixture_review",
            }
        ],
        "audit_outcome": [
            {
                "audit_id": "AUD0000000001",
                "review_id": "REV0000000001",
                "claim_id": "CLM0000000001V02",
                "outcome": "no_issue",
                "confirmed_amount": Decimal("0.00"),
                "outcome_date": date(2025, 2, 20),
            }
        ],
        "policy_assignment": [
            {
                "policy_assignment_id": "POL0000000001",
                "provider_id": "PRV000001",
                "policy_id": "POLICY_FIXTURE",
                "treatment_group": "comparison",
                "assignment_start_date": date(2025, 1, 1),
                "assignment_end_date": date(2025, 6, 30),
            }
        ],
        "anomaly_injection": [
            {
                "injection_id": "INJ0000000001",
                "rule_id": "PI010",
                "target_table": "claim_header",
                "target_record_id": "CLM0000000001V02",
                "claim_id": "CLM0000000001V02",
                "claim_line_id": None,
                "payment_transaction_id": None,
                "provider_id": "PRV000001",
                "reporting_period": date(2025, 2, 1),
                "injection_method": "field_mutation",
                "label_scope": "claim",
                "overlap_group": None,
                "expected_financial_exposure": Decimal("0.00"),
                "deterministic_seed": 20260724,
                "contract_version": 1,
                "synthetic_record": True,
            }
        ],
    }


def contracts() -> tuple[dict, dict, dict]:
    return (
        load_yaml(ROOT / "config/trusted_claims_contract.yml"),
        load_yaml(ROOT / "config/synthetic_data_contract.yml"),
        load_yaml(ROOT / "config/anomaly_injection_contract.yml"),
    )


def test_trusted_rows_are_deterministic_reconciled_and_version_safe() -> None:
    trusted_contract, operational, anomaly = contracts()
    source = source_fixture()
    first = generate_trusted_rows(source, trusted_contract, operational, anomaly)
    second = generate_trusted_rows(source, trusted_contract, operational, anomaly)

    assert first == second
    assert all(validate_trusted_rows(source, first, trusted_contract).values())
    assert [
        row["claim_id"] for row in first["fact_claim"] if row["is_current_version"]
    ] == ["CLM0000000001V02"]
    assert first["bridge_claim_anomaly"][0]["evaluation_only"] is True
    assert "rule_id" not in first["fact_claim"][0]


def test_trusted_builder_writes_repeatable_contract_parquet(tmp_path: Path) -> None:
    trusted_contract, operational, anomaly = contracts()
    source_root = tmp_path / "source"
    for name, rows in source_fixture().items():
        schema = (
            contract_table_schema(anomaly, name)
            if name == "anomaly_injection"
            else table_schema(operational, name)
        )
        write_parquet_atomic(rows, schema, source_root / f"{name}.parquet")
    contract_copy = deepcopy(trusted_contract)
    contract_path = tmp_path / "trusted_contract.yml"
    # The builder loads linked contracts using repository-relative paths.
    contract_path.write_text(
        (ROOT / "config/trusted_claims_contract.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    output_root = tmp_path / "trusted"
    arguments = {
        "contract_path": contract_path,
        "source_root": source_root,
        "output_root": output_root,
        "sample_root": tmp_path / "samples",
        "quality_report_path": tmp_path / "quality.json",
    }
    first = build_trusted_claims(**arguments)
    first_bytes = {
        name: (output_root / f"{name}.parquet").read_bytes()
        for name in trusted_contract["tables"]
    }
    second = build_trusted_claims(**arguments)

    assert contract_copy == trusted_contract
    assert first["all_checks_passed"] is True
    assert second["all_checks_passed"] is True
    assert first["tables"] == second["tables"]
    assert first_bytes == {
        name: (output_root / f"{name}.parquet").read_bytes()
        for name in trusted_contract["tables"]
    }
