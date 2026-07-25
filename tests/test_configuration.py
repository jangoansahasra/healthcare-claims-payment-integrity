from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = PROJECT_ROOT / "config" / "project.yml"
RULE_CONFIG = PROJECT_ROOT / "config" / "payment_integrity_rules.yml"


def load_yaml(path: Path) -> dict:
    """Load a YAML configuration file and require a mapping at its root."""
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(content, dict), f"{path.name} must contain a YAML mapping"
    return content


def test_required_configuration_files_exist() -> None:
    assert PROJECT_CONFIG.is_file()
    assert RULE_CONFIG.is_file()


def test_project_configuration_has_required_sections() -> None:
    config = load_yaml(PROJECT_CONFIG)

    assert {"project", "generation", "storage"} <= config.keys()


def test_project_configuration_values_are_valid() -> None:
    config = load_yaml(PROJECT_CONFIG)
    project = config["project"]
    generation = config["generation"]

    assert project["seed"] > 0
    assert project["currency"] == "USD"
    assert project["privacy_minimum_members"] >= 11
    assert generation["members"] > 0
    assert generation["providers"] > 0
    assert generation["claim_headers"] > 0
    assert 0 < generation["medical_claim_share"] < 1


def test_payment_integrity_rule_ids_are_unique() -> None:
    config = load_yaml(RULE_CONFIG)
    rules = config["rules"]
    rule_ids = [rule["rule_id"] for rule in rules]

    assert len(rule_ids) == len(set(rule_ids))


def test_payment_integrity_rules_have_required_metadata() -> None:
    config = load_yaml(RULE_CONFIG)
    required_fields = {
        "rule_id",
        "name",
        "enabled",
        "base_severity",
        "confidence",
    }
    valid_severities = {"low", "medium", "high", "critical"}

    for rule in config["rules"]:
        assert required_fields <= rule.keys()
        assert rule["base_severity"] in valid_severities
        assert isinstance(rule["enabled"], bool)
        assert 0 <= rule["confidence"] <= 1


def test_payment_integrity_rule_ids_follow_standard() -> None:
    config = load_yaml(RULE_CONFIG)

    for rule in config["rules"]:
        rule_id = rule["rule_id"]
        assert len(rule_id) == 5
        assert rule_id.startswith("PI")
        assert rule_id[2:].isdigit()