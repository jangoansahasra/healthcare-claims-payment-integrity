import os
from decimal import Decimal
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml
from src.transformation.build_cost_intelligence import read_trusted
from src.transformation.cost_intelligence import (
    OUTPUT_ORDER,
    generate_cost_intelligence,
    validate_cost_intelligence,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = load_yaml(ROOT / "config/cost_intelligence_contract.yml")


def trusted_root() -> Path:
    return Path(
        os.environ.get("TRUSTED_CLAIMS_TEST_ROOT", ROOT / "data/curated/trusted_claims")
    )


def test_cost_intelligence_is_deterministic_and_reconciled() -> None:
    source = read_trusted(trusted_root())
    first = generate_cost_intelligence(source, CONTRACT)
    second = generate_cost_intelligence(source, CONTRACT)
    assert first == second
    assert set(first) == set(OUTPUT_ORDER)
    assert all(validate_cost_intelligence(source, first).values())
    assert len(first["monthly_cost_utilization"]) == 72
    assert len(first["provider_service_concentration"]) == 144
    assert len(first["cost_early_warning_signal"]) == 288


def test_rates_concentration_decomposition_and_signals_are_valid() -> None:
    outputs = generate_cost_intelligence(read_trusted(trusted_root()), CONTRACT)
    assert all(
        row["eligible_member_months"] > 0 for row in outputs["monthly_cost_utilization"]
    )
    assert all(
        0 <= row["top_10_share"] <= 1 and 0 <= row["hhi"] <= 1
        for row in outputs["provider_service_concentration"]
    )
    assert all(
        abs(row["reconciliation_residual"]) <= Decimal("0.01")
        for row in outputs["cost_change_decomposition"]
    )
    assert {row["signal_status"] for row in outputs["cost_early_warning_signal"]} <= {
        "insufficient_history",
        "normal",
        "warning",
    }


def test_ground_truth_is_not_a_cost_intelligence_input() -> None:
    source = read_trusted(trusted_root())
    assert "bridge_claim_anomaly" not in source
    assert (
        CONTRACT["governance"]["ordinary_metrics_may_access_anomaly_ground_truth"]
        is False
    )
