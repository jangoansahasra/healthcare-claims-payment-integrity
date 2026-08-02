import re
from datetime import date
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "config" / "synthetic_data_contract.yml"
PROJECT_CONFIG_PATH = PROJECT_ROOT / "config" / "project.yml"

REQUIRED_TABLES = {
    "member",
    "plan",
    "provider",
    "provider_contract",
    "membership_month",
    "claim_header",
    "claim_line",
    "adjudication_event",
    "payment_transaction",
    "claim_review",
    "denial_outcome",
    "policy_assignment",
    "audit_outcome",
    "recovery_transaction",
}


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        content = yaml.safe_load(file)

    assert isinstance(content, dict)
    return content


def load_contract() -> dict:
    return load_yaml(CONTRACT_PATH)


def parse_reference(reference: str) -> tuple[str, list[str]]:
    match = re.fullmatch(r"([a-z_]+)\(([a-z_, ]+)\)", reference)

    assert match is not None, reference
    return match.group(1), [column.strip() for column in match.group(2).split(",")]


def test_contract_has_required_sections_and_tables() -> None:
    contract = load_contract()

    assert {
        "contract_version",
        "last_reviewed",
        "dataset",
        "governance",
        "generation",
        "identifier_formats",
        "allowed_values",
        "lifecycle_rules",
        "reconciliation_rules",
        "tables",
    } <= contract.keys()
    assert set(contract["tables"]) == REQUIRED_TABLES


def test_contract_matches_project_generation_controls() -> None:
    contract = load_contract()
    project = load_yaml(PROJECT_CONFIG_PATH)
    dataset = contract["dataset"]
    generation = contract["generation"]

    assert dataset["deterministic_seed"] == project["project"]["seed"]
    assert dataset["currency"] == project["project"]["currency"]
    assert str(dataset["reporting_start_date"]) == str(
        project["project"]["reporting_start_date"]
    )
    assert str(dataset["reporting_end_date"]) == str(
        project["project"]["reporting_end_date"]
    )
    assert str(dataset["policy_start_date"]) == str(
        project["generation"]["policy_start_date"]
    )
    assert generation["members"] == project["generation"]["members"]
    assert generation["providers"] == project["generation"]["providers"]
    assert generation["claim_headers"] == project["generation"]["claim_headers"]
    assert (
        generation["medical_claim_share"]
        == project["generation"]["medical_claim_share"]
    )
    assert generation["partition_columns"] == project["storage"]["partition_columns"]


def test_reporting_window_supports_pre_and_post_policy_periods() -> None:
    dataset = load_contract()["dataset"]
    start = date.fromisoformat(str(dataset["reporting_start_date"]))
    policy = date.fromisoformat(str(dataset["policy_start_date"]))
    end = date.fromisoformat(str(dataset["reporting_end_date"]))

    assert start < policy <= end
    assert (policy.year - start.year) * 12 + policy.month - start.month >= 12
    assert (end.year - policy.year) * 12 + end.month - policy.month + 1 >= 6


def test_primary_and_natural_keys_exist_and_are_nonnullable() -> None:
    for table_name, table in load_contract()["tables"].items():
        columns = table["columns"]

        assert table["grain"], table_name
        assert table["primary_key"], table_name

        for key_name in ("primary_key", "natural_key"):
            for column in table.get(key_name, []):
                assert column in columns, (table_name, column)
                assert columns[column]["nullable"] is False, (table_name, column)


def test_all_columns_have_governed_types_and_nullability() -> None:
    allowed_types = {
        "BOOLEAN",
        "DATE",
        "DECIMAL(18,2)",
        "DECIMAL(18,4)",
        "INTEGER",
        "SMALLINT",
        "TIMESTAMP",
        "VARCHAR",
    }

    for table_name, table in load_contract()["tables"].items():
        assert table["columns"], table_name
        for column_name, column in table["columns"].items():
            assert set(column) == {"type", "nullable"}, (table_name, column_name)
            assert column["type"] in allowed_types, (table_name, column_name)
            assert isinstance(column["nullable"], bool), (table_name, column_name)


def test_foreign_keys_reference_declared_columns() -> None:
    tables = load_contract()["tables"]

    for table_name, table in tables.items():
        for foreign_key in table.get("foreign_keys", []):
            target_table, target_columns = parse_reference(foreign_key["references"])
            source_columns = foreign_key["columns"]

            assert target_table in tables
            assert len(source_columns) == len(target_columns)
            assert set(source_columns) <= table["columns"].keys(), table_name
            assert set(target_columns) <= tables[target_table]["columns"].keys()


def test_identifier_formats_are_anchored_and_compile() -> None:
    formats = load_contract()["identifier_formats"]

    assert formats
    for identifier, pattern in formats.items():
        assert pattern.startswith("^") and pattern.endswith("$"), identifier
        re.compile(pattern)


def test_claim_versions_and_ledger_are_append_only() -> None:
    lifecycle = load_contract()["lifecycle_rules"]
    tables = load_contract()["tables"]

    assert lifecycle["preserve_all_claim_versions"] is True
    assert lifecycle["overwrite_prior_claim_versions"] is False
    assert lifecycle["require_prior_claim_for_version_above_one"] is True
    assert lifecycle["append_only_adjudication_events"] is True
    assert lifecycle["append_only_payment_transactions"] is True
    assert (
        "SUM(payment_transaction.signed_transaction_amount)"
        == lifecycle["net_paid_formula"]
    )
    assert tables["claim_header"]["columns"]["prior_claim_id"]["nullable"] is True
    assert (
        tables["payment_transaction"]["columns"]["signed_transaction_amount"]["type"]
        == "DECIMAL(18,2)"
    )


def test_date_roles_are_explicit_and_distinct() -> None:
    lifecycle = load_contract()["lifecycle_rules"]

    assert lifecycle["utilization_date_role"] == "claim_header.service_from_date"
    assert lifecycle["eligibility_date_role"] == "claim_header.service_from_date"
    assert lifecycle["operations_date_role"] == "claim_header.adjudication_date"
    assert lifecycle["finance_date_role"] == "payment_transaction.transaction_date"
    assert (
        len(
            {
                lifecycle["utilization_date_role"],
                lifecycle["operations_date_role"],
                lifecycle["finance_date_role"],
            }
        )
        == 3
    )
    assert lifecycle["prohibit_unnamed_claim_date"] is True


def test_financial_columns_use_fixed_decimal_types() -> None:
    contract = load_contract()
    monetary_type = contract["dataset"]["monetary_type"]

    assert monetary_type == "DECIMAL(18,2)"
    for table_name, table in contract["tables"].items():
        for column_name, column in table["columns"].items():
            if column_name.endswith("_amount"):
                assert column["type"] == monetary_type, (table_name, column_name)


def test_reconciliation_rule_ids_are_unique() -> None:
    rules = load_contract()["reconciliation_rules"]
    rule_ids = [rule["rule_id"] for rule in rules]

    assert len(rules) >= 8
    assert len(rule_ids) == len(set(rule_ids))
    assert all(rule_id.startswith("SYN") for rule_id in rule_ids)
    assert all(rule["expression"] for rule in rules)


def test_clean_baseline_is_separate_from_anomaly_injection() -> None:
    contract = load_contract()
    governance = contract["governance"]

    assert contract["dataset"]["role"] == "clean_operational_baseline"
    assert governance["clean_baseline_contains_intentional_anomalies"] is False
    assert governance["anomaly_injection_milestone"] == "M03"
    assert governance["contains_real_beneficiary_identifiers"] is False
    assert governance["contains_protected_health_information"] is False
    assert governance["contains_real_provider_identities"] is False
    assert governance["prohibit_real_provider_anomaly_attribution"] is True


def test_storage_and_publication_controls_are_safe() -> None:
    contract = load_contract()
    governance = contract["governance"]
    generation = contract["generation"]

    assert generation["deterministic_for_fixed_seed"] is True
    assert generation["stable_sort_before_write"] is True
    assert generation["output_format"] == "parquet"
    assert generation["compression"] == "zstd"
    assert generation["full_output_root"].startswith("data/generated/")
    assert generation["publishable_sample_root"].startswith("data/sample/")
    assert governance["minimum_public_member_count"] >= 11
    assert governance["full_output_committed_to_git"] is False
    assert governance["publishable_samples_are_synthetic_only"] is True
    assert governance["calibration_policy"]["copy_real_provider_records"] is False
    assert governance["calibration_policy"]["copy_real_beneficiary_records"] is False
