import subprocess
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/cost_intelligence_contract.yml"

REQUIRED_TABLES = {
    "monthly_cost_utilization",
    "monthly_payment_cash_flow",
    "provider_service_concentration",
    "cost_change_decomposition",
    "cost_early_warning_signal",
}


def load_contract() -> dict:
    return load_yaml(CONTRACT_PATH)


def test_contract_defines_complete_m06_outputs() -> None:
    model = load_contract()

    assert model["dataset"]["milestone"] == "M06"
    assert model["dataset"]["trusted_contract"] == (
        "config/trusted_claims_contract.yml"
    )
    assert set(model["tables"]) == REQUIRED_TABLES
    assert len(model["metric_definitions"]) >= 8


def test_every_table_has_explicit_grain_keys_and_supported_types() -> None:
    supported = {
        "BIGINT",
        "DATE",
        "DECIMAL(18,2)",
        "DECIMAL(18,4)",
        "DECIMAL(18,6)",
        "INTEGER",
        "VARCHAR",
    }
    for table_name, table in load_contract()["tables"].items():
        assert table["grain"], table_name
        assert table["primary_key"] == table["natural_key"]
        for key in table["primary_key"]:
            assert key in table["columns"]
            assert table["columns"][key]["nullable"] is False
        for column, definition in table["columns"].items():
            assert set(definition) == {"type", "nullable"}, (table_name, column)
            assert definition["type"] in supported, (table_name, column)


def test_pmpm_and_utilization_use_member_month_exposure() -> None:
    model = load_contract()
    metrics = model["metric_definitions"]
    population = model["population_policy"]

    assert population["claim_scope"] == "current_version_only"
    assert population["eligibility_status"] == "active"
    assert population["member_month_grain"] == [
        "member_key",
        "plan_key",
        "coverage_month",
    ]
    for name in ("allowed_pmpm", "paid_pmpm"):
        assert metrics[name]["denominator"] == (
            "eligible member months by coverage month and plan"
        )
    assert metrics["claims_per_1000"]["formula"] == (
        "claim_count * 1000 / eligible_member_months"
    )
    assert metrics["units_per_1000"]["formula"] == (
        "service_units * 1000 / eligible_member_months"
    )


def test_service_and_payment_date_roles_are_separate() -> None:
    model = load_contract()
    population = model["population_policy"]

    assert population["service_date_role"] == "fact_claim.service_date_key"
    assert population["payment_date_role"] == (
        "fact_payment_transaction.transaction_date_key"
    )
    assert model["governance"]["service_and_payment_date_metrics_published_separately"]
    assert "service_month" in model["tables"]["monthly_cost_utilization"]["columns"]
    assert "payment_month" in model["tables"]["monthly_payment_cash_flow"]["columns"]


def test_financial_measures_and_reconciliation_are_explicit() -> None:
    model = load_contract()
    monthly = model["tables"]["monthly_cost_utilization"]["columns"]
    cash = model["tables"]["monthly_payment_cash_flow"]["columns"]

    for column in ("allowed_amount", "paid_amount"):
        assert monthly[column]["type"] == "DECIMAL(18,2)"
    assert cash["net_payment_cash_flow"]["type"] == "DECIMAL(18,2)"
    assert model["decomposition_policy"]["financial_tolerance"] == 0.01


def test_price_utilization_and_mix_decomposition_reconciles_by_contract() -> None:
    policy = load_contract()["decomposition_policy"]

    assert policy["comparison_interval"] == "year_over_year"
    assert policy["base_period"] == "prior_year_same_month"
    assert policy["price_measure"] == "allowed_amount / service_units"
    assert policy["utilization_measure"] == ("service_units / eligible_member_months")
    assert policy["reconciliation_formula"] == (
        "price_effect + utilization_effect + mix_effect = total_change"
    )
    assert policy["zero_unit_result"] is None


def test_concentration_metrics_are_governed() -> None:
    metrics = load_contract()["metric_definitions"]

    for name in ("provider_concentration", "service_concentration"):
        assert metrics[name]["measure"] == "allowed_amount"
        assert set(metrics[name]["formulas"]) == {"top_10_share", "hhi"}
        assert metrics[name]["formulas"]["hhi"] == (
            "sum squared provider allowed amount shares"
            if name == "provider_concentration"
            else "sum squared service allowed amount shares"
        )


def test_early_warning_history_and_thresholds_are_explicit() -> None:
    policy = load_contract()["early_warning_policy"]

    assert policy["minimum_history_months"] == 6
    assert policy["baseline_window_months"] == 12
    assert policy["exclude_current_month_from_baseline"] is True
    assert policy["minimum_eligible_member_months"] == 100
    assert policy["robust_center"] == "median"
    assert policy["robust_scale"] == "median_absolute_deviation"
    assert policy["warning_z_score"] == 3.0
    assert policy["minimum_relative_change"] == 0.20


def test_ground_truth_privacy_and_small_cell_controls_are_explicit() -> None:
    governance = load_contract()["governance"]

    assert governance["synthetic_records_only"] is True
    assert governance["contains_protected_health_information"] is False
    assert governance["ordinary_metrics_may_access_anomaly_ground_truth"] is False
    assert governance["suppress_small_cells"] is True
    assert governance["minimum_publishable_member_count"] == 11


def test_quality_determinism_and_storage_controls() -> None:
    model = load_contract()
    checks = [row["check_id"] for row in model["quality_checks"]]

    assert len(checks) >= 12
    assert len(checks) == len(set(checks))
    assert all(check.startswith("CI") for check in checks)
    assert model["dataset"]["output_format"] == "parquet"
    assert model["dataset"]["compression"] == "zstd"
    assert model["dataset"]["full_output_committed_to_git"] is False
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "data/curated/cost_intelligence/monthly_cost_utilization.parquet",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
