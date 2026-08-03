import re
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/anomaly_injection_contract.yml"
RULES_PATH = ROOT / "config/payment_integrity_rules.yml"
BASELINE_REPORT_PATH = (
    ROOT / "data/metadata/quality/synthetic_operational_baseline.json"
)


def test_all_governed_rules_have_one_scenario_contract() -> None:
    contract = load_yaml(CONTRACT_PATH)
    registry = load_yaml(RULES_PATH)
    configured = [item["rule_id"] for item in contract["scenarios"]]
    governed = [item["rule_id"] for item in registry["rules"] if item["enabled"]]

    assert configured == governed
    assert len(configured) == len(set(configured)) == 10


def test_every_scenario_defines_target_eligibility_and_exposure() -> None:
    contract = load_yaml(CONTRACT_PATH)
    methods = set(contract["allowed_values"]["injection_method"])
    scopes = set(contract["allowed_values"]["label_scope"])

    for scenario in contract["scenarios"]:
        assert scenario["target_table"]
        assert scenario["target_grain"]
        assert scenario["injection_method"] in methods
        assert scenario["label_scope"] in scopes
        assert scenario["eligibility"]
        assert scenario["exclusions"]
        assert scenario["mutations"]
        assert scenario["expected_violation"]
        assert scenario["financial_exposure_formula"] is not None


def test_overlap_is_prohibited_except_for_named_combinations() -> None:
    contract = load_yaml(CONTRACT_PATH)
    policy = contract["overlap_policy"]
    rule_ids = {item["rule_id"] for item in contract["scenarios"]}

    assert contract["governance"]["default_overlap_policy"] == "prohibited"
    assert policy["default"] == "prohibited"
    assert policy["require_overlap_group"] is True
    assert all(
        set(combination) <= rule_ids
        for combination in policy["allowed_rule_combinations"]
    )
    assert set(policy["selection_precedence"]) == rule_ids


def test_ground_truth_tables_have_keys_and_required_lineage() -> None:
    contract = load_yaml(CONTRACT_PATH)
    tables = contract["tables"]

    assert set(tables) == {
        "anomaly_injection",
        "anomaly_field_change",
        "baseline_hash_manifest",
    }
    assert tables["anomaly_injection"]["primary_key"] == ["injection_id"]
    assert tables["anomaly_field_change"]["primary_key"] == [
        "injection_id",
        "change_sequence_number",
    ]
    assert tables["baseline_hash_manifest"]["primary_key"] == ["table_name"]
    change_columns = tables["anomaly_field_change"]["columns"]
    assert {"before_value", "after_value", "governed_value_type"} <= set(change_columns)


def test_identifier_patterns_are_anchored_and_valid() -> None:
    patterns = load_yaml(CONTRACT_PATH)["identifier_formats"]

    assert all(
        pattern.startswith("^") and pattern.endswith("$")
        for pattern in patterns.values()
    )
    assert re.fullmatch(patterns["injection_id"], "INJ0000000001")
    assert re.fullmatch(patterns["claim_id"], "CLM0000000001V01")
    assert re.fullmatch(patterns["claim_line_id"], "LIN000000000001")
    assert re.fullmatch(patterns["payment_transaction_id"], "PAY000000000001")
    assert re.fullmatch(patterns["provider_id"], "PRV000001")


def test_clean_baseline_report_can_seed_complete_hash_manifest() -> None:
    import json

    contract = load_yaml(CONTRACT_PATH)
    report = json.loads(BASELINE_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["all_checks_passed"] is True
    assert len(report["tables"]) == 14
    assert all(details["row_count"] >= 0 for details in report["tables"].values())
    assert all(
        re.fullmatch(r"[0-9a-f]{64}", details["content_sha256"])
        for details in report["tables"].values()
    )
    assert contract["dataset"]["baseline_quality_report"] == (
        "data/metadata/quality/synthetic_operational_baseline.json"
    )


def test_privacy_storage_and_clean_baseline_controls_are_explicit() -> None:
    contract = load_yaml(CONTRACT_PATH)
    governance = contract["governance"]

    assert governance["contains_real_beneficiary_identifiers"] is False
    assert governance["contains_protected_health_information"] is False
    assert governance["contains_real_provider_identities"] is False
    assert governance["prohibit_real_provider_anomaly_attribution"] is True
    assert governance["preserve_clean_baseline_files"] is True
    assert governance["verify_baseline_hashes_before_and_after"] is True
    assert governance["full_output_committed_to_git"] is False
    assert (
        contract["dataset"]["clean_baseline_root"]
        != contract["dataset"]["anomalous_output_root"]
    )


def test_configured_weights_and_defaults_are_governed() -> None:
    contract = load_yaml(CONTRACT_PATH)

    assert contract["scenario_defaults"]["target_count"] > 0
    assert contract["scenario_defaults"]["allow_overlap"] is False
    assert contract["scenario_defaults"]["retain_before_after_lineage"] is True
    assert contract["scenario_defaults"]["unchanged_fields_must_match_baseline"] is True
    assert contract["governance"]["ground_truth_committed_to_git"] is False
