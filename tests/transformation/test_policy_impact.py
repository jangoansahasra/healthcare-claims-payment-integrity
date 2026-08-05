import os
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml
from src.transformation.build_policy_impact import read_inputs
from src.transformation.policy_impact import (
    OUTCOMES,
    build_provider_month_panel,
    estimate_policy_impact,
    validate_policy_impact,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = load_yaml(ROOT / "config/policy_impact_contract.yml")


def trusted_root() -> Path:
    return Path(
        os.environ.get("TRUSTED_CLAIMS_TEST_ROOT", ROOT / "data/curated/trusted_claims")
    )


def test_panel_is_balanced_with_frozen_cohorts_and_valid_interaction() -> None:
    panel = build_provider_month_panel(read_inputs(trusted_root()), CONTRACT)
    assert len(panel) == 3600
    assert len({row["provider_key"] for row in panel}) == 200
    assert {row["treatment_group"] for row in panel} == {"treated", "comparison"}
    assert all(
        row["treatment_post"]
        == (row["treatment_indicator"] and row["post_policy_indicator"])
        for row in panel
    )
    assert {
        sum(row["provider_key"] == provider for row in panel)
        for provider in range(1, 201)
    } == {18}


def test_estimates_are_deterministic_complete_and_diagnosed() -> None:
    panel = build_provider_month_panel(read_inputs(trusted_root()), CONTRACT)
    first = estimate_policy_impact(panel, CONTRACT)
    second = estimate_policy_impact(panel, CONTRACT)
    assert first == second
    assert all(validate_policy_impact(first).values())
    assert len(first["policy_effect_estimate"]) == 15
    assert len(first["event_study_estimate"]) == 85
    assert len(first["policy_diagnostic"]) == 10
    assert {row["outcome_name"] for row in first["policy_effect_estimate"]} == set(
        OUTCOMES
    )
    assert all(row["event_time"] != -1 for row in first["event_study_estimate"])
    assert {row["diagnostic_name"] for row in first["policy_diagnostic"]} == {
        "parallel_trends",
        "placebo_policy_date",
    }


def test_ground_truth_is_not_an_analysis_input() -> None:
    source = read_inputs(trusted_root())
    assert "bridge_claim_anomaly" not in source
    assert (
        CONTRACT["governance"]["model_inputs_may_access_anomaly_ground_truth"] is False
    )
