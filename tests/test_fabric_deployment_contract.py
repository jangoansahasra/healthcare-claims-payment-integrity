import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/fabric_deployment_contract.yml"
EXECUTION_EVIDENCE_PATH = ROOT / "data/metadata/quality/fabric_execution.json"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def load_source_tables(path: str) -> dict:
    source = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    return source["tables"]


def test_execution_status_matches_real_fabric_evidence() -> None:
    contract = load_contract()
    readiness = contract["verified_readiness"]

    assert contract["deployment"]["execution_status"] == "passed"
    assert contract["deployment"]["provisioning_performed"] is True
    assert contract["deployment"]["cloud_success_claimed"] is True
    assert readiness["fabric"]["license_type"] == "Power BI Individual Trial"
    assert readiness["fabric"]["trial_activated"] is True
    assert readiness["fabric"]["capacity_status"] == "active"
    assert readiness["fabric"]["capacity_region"] == "North Central US"
    assert readiness["fabric"]["workspace_created"] is True
    assert readiness["fabric"]["notebook_executed"] is True
    assert readiness["fabric"]["pipeline_executed"] is True
    assert readiness["azure"]["subscription_offer"] == "Azure for Students"
    assert readiness["azure"]["subscription_status"] == "active"
    assert readiness["azure"]["paid_resource_created_for_m09"] is False


def test_sanitized_execution_evidence_reconciles() -> None:
    evidence = json.loads(EXECUTION_EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert evidence["execution_status"] == "passed"
    assert evidence["table_count"] == 26
    assert evidence["ordinary_table_count"] == 23
    assert evidence["restricted_table_count"] == 3
    assert evidence["reconciliation_result_count"] == 33
    assert evidence["reconciliation_passed_count"] == 33
    assert evidence["reconciliation_failed_count"] == 0
    assert evidence["notebook_status"] == "succeeded"
    assert evidence["pipeline_status"] == "succeeded"
    assert evidence["run_identifiers_retained_outside_git"] is True
    assert evidence["screenshots_retained_outside_git"] is True
    assert evidence["teardown_status"] == "retained_for_m10"
    assert evidence["paid_resource_cost_usd"] == 0.0


def test_sensitive_identifiers_are_prohibited() -> None:
    contract = load_contract()
    prohibited = set(contract["verified_readiness"]["prohibited_evidence_fields"])

    assert {"user_email", "subscription_id", "tenant_id", "access_token"} <= prohibited
    assert contract["governance"]["prohibit_secrets_in_git_or_logs"] is True
    assert contract["governance"]["prohibit_unredacted_portal_screenshots"] is True


def test_cost_controls_precede_provisioning() -> None:
    controls = load_contract()["cost_control"]

    assert controls["preferred_capacity"] == "Fabric Trial"
    assert controls["trial_activation_requires_contract_merged"] is True
    assert controls["paid_provisioning_requires_explicit_approval"] is True
    assert controls["azure_budget_required_before_paid_provisioning"] is True
    assert controls["budget_alert_threshold_percentages"] == [50, 80, 100]
    assert controls["pause_compute_after_session"] is True
    assert controls["teardown_after_evidence_capture"] is True


def test_artifact_names_and_order_are_deterministic() -> None:
    contract = load_contract()
    names = contract["naming"]
    order = contract["deployment_order"]

    assert names["workspace"] == "hcpi-portfolio-m09"
    assert names["lakehouse"] == "lh_hcpi_curated"
    assert names["notebook"].startswith("nb_")
    assert names["pipeline"].startswith("pl_")
    assert order[0] == "create_trial_capacity_after_approval"
    assert order[-1] == "verify_final_cost"
    assert len(order) == len(set(order))


def test_cloud_mappings_match_authoritative_contract_keys() -> None:
    contract = load_contract()
    authority = contract["architecture"]["local_schema_authority"]

    domains = ("trusted", "payment_integrity", "cost_intelligence", "policy_impact")
    for domain in domains:
        source_tables = load_source_tables(authority[domain])
        mapped_tables = contract["schemas"][domain]["tables"]
        for table_name, mapping in mapped_tables.items():
            assert table_name in source_tables
            assert mapping["primary_key"] == source_tables[table_name]["primary_key"]


def test_all_ordinary_domain_tables_are_mapped() -> None:
    contract = load_contract()
    authority = contract["architecture"]["local_schema_authority"]
    excluded = {
        "trusted": {"bridge_claim_anomaly"},
        "payment_integrity": {"finding_ground_truth_match", "rule_evaluation"},
        "cost_intelligence": set(),
        "policy_impact": set(),
    }

    for domain, exclusions in excluded.items():
        source_names = set(load_source_tables(authority[domain])) - exclusions
        mapped_names = set(contract["schemas"][domain]["tables"])
        assert mapped_names == source_names


def test_evaluation_tables_are_isolated() -> None:
    contract = load_contract()
    restricted = contract["schemas"]["evaluation_only"]

    assert restricted["access"] == "restricted_not_for_ordinary_analytics"
    assert set(restricted["tables"]) == {
        "bridge_claim_anomaly",
        "finding_ground_truth_match",
        "rule_evaluation",
    }
    governance = contract["governance"]
    assert governance["ordinary_surfaces_may_access_anomaly_ground_truth"] is False


def test_reconciliation_tolerances_and_checks_are_explicit() -> None:
    reconciliation = load_contract()["reconciliation"]
    check_ids = [item["check_id"] for item in reconciliation["checks"]]

    assert reconciliation["count_tolerance"] == 0
    assert reconciliation["distinct_primary_key_tolerance"] == 0
    assert reconciliation["financial_tolerance"] == 0.01
    assert check_ids == [f"FAB{number:03d}" for number in range(1, 13)]


def test_service_and_payment_date_roles_remain_distinct() -> None:
    contract = load_contract()
    cost_tables = contract["schemas"]["cost_intelligence"]["tables"]

    assert cost_tables["monthly_cost_utilization"]["date_role"] == "service_month"
    assert cost_tables["monthly_payment_cash_flow"]["date_role"] == "payment_month"
    governance = contract["governance"]
    assert governance["service_and_payment_date_roles_must_remain_separate"] is True


def test_cloud_success_requires_real_execution_evidence() -> None:
    evidence = load_contract()["evidence"]
    required = set(evidence["required_for_cloud_success"])

    assert {"workspace_name", "capacity_type", "region"} <= required
    assert {"notebook_run_id", "pipeline_run_id"} <= required
    completion_evidence = {
        "table_reconciliation_results",
        "teardown_status",
        "final_cost_status",
    }
    assert completion_evidence <= required
    assert evidence["screenshot_redaction_required"] is True
    assert evidence["artifact_hash_algorithm"] == "sha256"
