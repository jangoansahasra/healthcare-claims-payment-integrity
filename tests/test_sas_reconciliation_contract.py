import subprocess
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "config/sas_reconciliation_contract.yml"


def contract() -> dict:
    return load_yaml(PATH)


def test_runtime_status_is_truthful_and_requires_real_evidence() -> None:
    runtime = contract()["runtime"]
    assert runtime["local_runtime_available"] is False
    assert runtime["local_probe_result"] == "not_found"
    assert runtime["execution_status"] == "not_executed"
    assert runtime["success_requires_real_sas_log"] is True
    assert runtime["prohibit_simulated_success_evidence"] is True
    assert "sas_version" in runtime["required_evidence"]
    assert "sas_log_path" in runtime["required_evidence"]


def test_tolerances_separate_counts_finance_rates_and_statistics() -> None:
    values = contract()["tolerances"]
    assert values["row_count_absolute"] == 0
    assert values["distinct_key_absolute"] == 0
    assert values["financial_absolute"] == 0.01
    assert values["rate_absolute"] == 0.0001
    assert values["coefficient_absolute"] == 0.001
    assert values["p_value_absolute"] == 0.001


def test_portable_exchange_contract_is_explicit() -> None:
    exchange = contract()["portable_exchange"]
    assert exchange["format"] == "csv"
    assert exchange["encoding"] == "utf-8"
    assert exchange["header"] is True
    assert exchange["date_format"] == "YYYY-MM-DD"
    assert exchange["missing_value"] == "empty_field"
    assert exchange["input_manifest_required"] is True
    assert exchange["sha256_required"] is True


def test_program_order_is_unique_complete_and_deterministic() -> None:
    programs = contract()["program_order"]
    sequences = [row["sequence"] for row in programs]
    paths = [row["path"] for row in programs]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    assert len(paths) == len(set(paths))
    assert paths[0].endswith("00_setup.sas")
    assert paths[-1].endswith("90_publish_results.sas")


def test_metric_registry_covers_all_required_domains_and_tolerances() -> None:
    model = contract()
    metrics = model["metrics"]
    identifiers = [row["metric_id"] for row in metrics]
    assert len(identifiers) == 12
    assert len(identifiers) == len(set(identifiers))
    assert {row["domain"] for row in metrics} == {
        "trusted_claims",
        "membership",
        "cost_intelligence",
        "payment_integrity",
        "policy_impact",
    }
    assert all(row["tolerance"] in model["tolerances"] for row in metrics)


def test_result_schema_has_keys_values_tolerance_and_status() -> None:
    result = contract()["result_schema"]
    assert result["primary_key"] == [
        "execution_id",
        "metric_id",
        "comparison_scope",
    ]
    assert result["columns"]["passed"] == {"type": "BOOLEAN", "nullable": False}
    assert {
        "python_value",
        "sas_value",
        "absolute_difference",
        "tolerance",
    } <= set(result["columns"])


def test_log_policy_prohibits_errors_and_conversion_warnings() -> None:
    policy = contract()["log_policy"]
    assert "ERROR:" in policy["fail_patterns"]
    assert "WARNING:" in policy["review_patterns"]
    assert policy["unintended_conversion_warnings_allowed"] is False
    assert policy["zero_errors_required"] is True
    assert policy["log_checksum_required"] is True


def test_quality_storage_and_local_probe_controls() -> None:
    model = contract()
    checks = [row["check_id"] for row in model["quality_checks"]]
    assert len(checks) >= 12 and len(checks) == len(set(checks))
    assert all(value.startswith("SR") for value in checks)
    assert model["dataset"]["full_generated_inputs_committed_to_git"] is False
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "data/generated/sas_reconciliation/input/fact_claim.csv",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
