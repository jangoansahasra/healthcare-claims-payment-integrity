import re
import subprocess
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/payment_integrity_contract.yml"
RULES_PATH = ROOT / "config/payment_integrity_rules.yml"

REQUIRED_TABLES = {
    "rule_run",
    "rule_finding",
    "finding_evidence",
    "finding_ground_truth_match",
    "rule_evaluation",
}
RULE_IDS = {f"PI{number:03d}" for number in range(1, 11)}


def load(path: Path) -> dict:
    return load_yaml(path)


def parse_reference(reference: str) -> tuple[str, list[str]]:
    match = re.fullmatch(r"([a-z_]+)\(([a-z_, ]+)\)", reference)
    assert match is not None, reference
    return match.group(1), [value.strip() for value in match.group(2).split(",")]


def test_contract_defines_complete_m05_outputs() -> None:
    model = load(CONTRACT_PATH)

    assert {
        "contract_version",
        "dataset",
        "governance",
        "execution_policy",
        "matching_policy",
        "evaluation_policy",
        "tables",
        "quality_checks",
    } <= model.keys()
    assert model["dataset"]["milestone"] == "M05"
    assert set(model["tables"]) == REQUIRED_TABLES


def test_all_enabled_rules_are_governed_by_contract() -> None:
    model = load(CONTRACT_PATH)
    registry = load(RULES_PATH)
    configured = {rule["rule_id"] for rule in registry["rules"] if rule["enabled"]}

    assert configured == RULE_IDS
    assert set(model["execution_policy"]["enabled_rule_ids"]) == configured
    assert model["execution_policy"]["enabled_rule_source"] == (
        "config/payment_integrity_rules.yml"
    )


def test_every_table_has_grain_keys_and_supported_columns() -> None:
    supported = {
        "BIGINT",
        "BOOLEAN",
        "DATE",
        "DECIMAL(18,2)",
        "DECIMAL(18,4)",
        "INTEGER",
        "VARCHAR",
    }
    for table_name, table in load(CONTRACT_PATH)["tables"].items():
        assert table["grain"], table_name
        assert table["primary_key"], table_name
        for column_name, definition in table["columns"].items():
            assert set(definition) == {"type", "nullable"}
            assert definition["type"] in supported, (table_name, column_name)
            assert isinstance(definition["nullable"], bool)
        for key_type in ("primary_key", "natural_key"):
            for column in table[key_type]:
                assert column in table["columns"], (table_name, column)
                assert table["columns"][column]["nullable"] is False


def test_foreign_keys_resolve_with_compatible_columns() -> None:
    tables = load(CONTRACT_PATH)["tables"]

    for table_name, table in tables.items():
        for foreign_key in table.get("foreign_keys", []):
            target_table, target_columns = parse_reference(foreign_key["references"])
            source_columns = foreign_key["columns"]
            assert target_table in tables
            assert len(source_columns) == len(target_columns)
            for source, target in zip(source_columns, target_columns, strict=True):
                assert source in table["columns"]
                assert target in tables[target_table]["columns"]
                assert (
                    table["columns"][source]["type"]
                    == (tables[target_table]["columns"][target]["type"])
                ), table_name


def test_findings_are_explainable_and_financially_typed() -> None:
    model = load(CONTRACT_PATH)
    finding = model["tables"]["rule_finding"]
    evidence = model["tables"]["finding_evidence"]

    assert model["execution_policy"]["one_finding_per_rule_and_target"] is True
    assert model["execution_policy"]["preserve_all_supporting_evidence"] is True
    assert finding["columns"]["amount_at_risk"]["type"] == "DECIMAL(18,2)"
    assert finding["columns"]["confidence"]["type"] == "DECIMAL(18,4)"
    assert finding["columns"]["explanation"]["nullable"] is False
    assert {"observed_value", "threshold_value", "source_record_id"} <= set(
        evidence["columns"]
    )


def test_ground_truth_cannot_leak_into_detection() -> None:
    governance = load(CONTRACT_PATH)["governance"]
    run = load(CONTRACT_PATH)["tables"]["rule_run"]

    assert governance["detection_phase_may_access_ground_truth"] is False
    assert governance["freeze_findings_before_evaluation"] is True
    assert governance["evaluation_phase_may_access_ground_truth"] is True
    assert governance["prohibit_ground_truth_as_rule_input"] is True
    assert run["columns"]["findings_frozen"]["nullable"] is False
    assert run["columns"]["ground_truth_accessed_during_detection"]["nullable"] is False


def test_exact_matching_policy_covers_every_label_scope() -> None:
    policy = load(CONTRACT_PATH)["matching_policy"]

    assert policy["method"] == "exact_rule_and_canonical_target"
    assert policy["require_same_rule_id"] is True
    assert policy["require_same_label_scope"] is True
    assert policy["multi_label_targets_evaluated_per_rule"] is True
    assert set(policy["canonical_target_by_scope"]) == {
        "claim",
        "claim_line",
        "payment_transaction",
        "provider",
        "provider_period",
    }
    assert policy["canonical_target_by_scope"]["provider_period"] == [
        "provider_id",
        "reporting_period",
    ]


def test_metric_formulas_thresholds_and_audit_rows_are_explicit() -> None:
    policy = load(CONTRACT_PATH)["evaluation_policy"]
    evaluation = load(CONTRACT_PATH)["tables"]["rule_evaluation"]
    matches = load(CONTRACT_PATH)["tables"]["finding_ground_truth_match"]

    assert policy["thresholds"] == {
        "minimum_precision": 0.70,
        "minimum_recall": 0.85,
        "maximum_false_positive_rate": 0.10,
    }
    assert policy["precision_formula"] == (
        "true_positives / (true_positives + false_positives)"
    )
    assert policy["recall_formula"] == (
        "true_positives / (true_positives + false_negatives)"
    )
    assert policy["false_positive_rate_formula"] == (
        "false_positives / (false_positives + true_negatives)"
    )
    assert {
        "true_positive_count",
        "false_positive_count",
        "false_negative_count",
    } <= set(evaluation["columns"])
    assert matches["columns"]["evaluation_only"] == {
        "type": "BOOLEAN",
        "nullable": False,
    }


def test_quality_privacy_determinism_and_storage_controls() -> None:
    model = load(CONTRACT_PATH)
    identifiers = [row["check_id"] for row in model["quality_checks"]]

    assert len(identifiers) >= 12
    assert len(identifiers) == len(set(identifiers))
    assert all(identifier.startswith("PIE") for identifier in identifiers)
    assert model["dataset"]["deterministic_seed"] == 20260724
    assert model["dataset"]["output_format"] == "parquet"
    assert model["dataset"]["compression"] == "zstd"
    assert model["dataset"]["full_output_committed_to_git"] is False
    assert model["governance"]["synthetic_records_only"] is True
    assert model["governance"]["contains_protected_health_information"] is False
    ignored = subprocess.run(
        ["git", "check-ignore", "data/curated/payment_integrity/rule_finding.parquet"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
