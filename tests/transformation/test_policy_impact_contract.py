import subprocess
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "config/policy_impact_contract.yml"


def contract() -> dict:
    return load_yaml(PATH)


def test_contract_defines_m07_panel_estimators_and_outputs() -> None:
    model = contract()
    assert model["dataset"]["milestone"] == "M07"
    assert set(model["tables"]) == {
        "provider_month_policy_panel",
        "policy_effect_estimate",
        "event_study_estimate",
        "policy_diagnostic",
    }
    assert set(model["outcomes"]) == {
        "paid_pmpm",
        "allowed_pmpm",
        "claims_per_1000",
        "denial_rate",
        "review_rate",
        "zero_denominator_result",
    }


def test_design_locks_cohorts_timing_and_balanced_window() -> None:
    design = contract()["design"]
    assert str(design["policy_start_date"]) == "2026-01-01"
    assert design["panel_grain"] == ["provider_key", "reporting_month"]
    assert design["treatment_value"] == "treated"
    assert design["comparison_value"] == "comparison"
    assert design["cohorts_mutually_exclusive"] is True
    assert design["required_pre_policy_months"] == 12
    assert design["required_post_policy_months"] == 6
    assert design["event_time_reference"] == -1
    assert design["balanced_panel_required"] is True
    assert design["member_attribution"]["method"] == (
        "plurality_of_pre_policy_paid_claims"
    )


def test_outcome_denominators_and_date_roles_are_explicit() -> None:
    outcomes = contract()["outcomes"]
    for name in ("paid_pmpm", "allowed_pmpm", "claims_per_1000"):
        assert "eligible member months" in outcomes[name]["denominator"]
        assert outcomes[name]["date_role"] == "service_date"
    assert outcomes["denial_rate"]["denominator"] == "all current logical claims"
    assert outcomes["review_rate"]["date_role"] == "review_selected_date"
    assert outcomes["zero_denominator_result"] is None


def test_primary_did_uses_fixed_effects_and_provider_clustered_errors() -> None:
    estimator = contract()["primary_estimator"]
    assert estimator["method"] == "two_way_fixed_effects_difference_in_differences"
    assert estimator["treatment_post"] == (
        "treatment_indicator * post_policy_indicator"
    )
    assert estimator["provider_fixed_effects"] is True
    assert estimator["month_fixed_effects"] is True
    assert estimator["standard_errors"] == "cluster_robust"
    assert estimator["cluster_unit"] == "provider_key"
    assert estimator["confidence_level"] == 0.95


def test_event_study_pretrend_placebo_and_sensitivity_are_governed() -> None:
    model = contract()
    event = model["event_study"]
    diagnostics = model["diagnostics"]
    assert event["reference_event_time"] == -1
    assert (event["minimum_event_time"], event["maximum_event_time"]) == (-12, 5)
    assert -1 not in diagnostics["parallel_trends"]["tested_event_times"]
    assert diagnostics["parallel_trends"]["pass_rule"] == (
        "p_value >= significance_level"
    )
    assert str(diagnostics["placebo"]["policy_start_date"]) == "2025-07-01"
    assert len(diagnostics["sensitivity"]["specifications"]) == 3


def test_tables_have_supported_typed_keys_and_inference_fields() -> None:
    supported = {"BIGINT", "BOOLEAN", "DATE", "DECIMAL(18,4)", "INTEGER", "VARCHAR"}
    for name, table in contract()["tables"].items():
        assert table["primary_key"] == table["natural_key"]
        for key in table["primary_key"]:
            assert table["columns"][key]["nullable"] is False
        assert all(value["type"] in supported for value in table["columns"].values()), (
            name
        )
    estimate = contract()["tables"]["policy_effect_estimate"]["columns"]
    assert {
        "coefficient",
        "standard_error",
        "confidence_interval_lower",
        "confidence_interval_upper",
        "p_value",
        "provider_count",
        "observation_count",
    } <= set(estimate)


def test_governance_quality_determinism_and_storage_controls() -> None:
    model = contract()
    checks = [row["check_id"] for row in model["quality_checks"]]
    assert len(checks) >= 12 and len(checks) == len(set(checks))
    assert all(value.startswith("PA") for value in checks)
    assert model["governance"]["model_inputs_may_access_anomaly_ground_truth"] is False
    assert model["governance"]["treatment_assignment_frozen_before_outcomes"] is True
    assert model["dataset"]["full_output_committed_to_git"] is False
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "data/curated/policy_impact/policy_effect_estimate.parquet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
