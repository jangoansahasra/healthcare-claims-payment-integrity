import re
import subprocess
from pathlib import Path

from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "config/trusted_claims_contract.yml"

REQUIRED_TABLES = {
    "dim_member",
    "dim_provider",
    "dim_plan",
    "dim_date",
    "dim_service",
    "fact_membership_month",
    "fact_claim",
    "fact_claim_line",
    "fact_payment_transaction",
    "fact_claim_review",
    "bridge_provider_policy",
    "bridge_claim_anomaly",
}


def contract() -> dict:
    return load_yaml(CONTRACT_PATH)


def parse_reference(reference: str) -> tuple[str, list[str]]:
    match = re.fullmatch(r"([a-z_]+)\(([a-z_, ]+)\)", reference)

    assert match is not None, reference
    return match.group(1), [column.strip() for column in match.group(2).split(",")]


def test_contract_has_complete_trusted_star() -> None:
    model = contract()

    assert {
        "contract_version",
        "dataset",
        "governance",
        "key_policy",
        "claim_version_policy",
        "date_roles",
        "measure_policy",
        "tables",
        "reconciliation_checks",
    } <= model.keys()
    assert set(model["tables"]) == REQUIRED_TABLES
    assert model["dataset"]["milestone"] == "M04"


def test_every_table_has_governed_grain_and_keys() -> None:
    for table_name, table in contract()["tables"].items():
        columns = table["columns"]

        assert table["grain"], table_name
        assert table["primary_key"], table_name
        for key_type in ("primary_key", "natural_key"):
            for column in table.get(key_type, []):
                assert column in columns, (table_name, column)
                assert columns[column]["nullable"] is False, (table_name, column)


def test_columns_have_supported_types_and_nullability() -> None:
    supported = {
        "BIGINT",
        "BOOLEAN",
        "DATE",
        "DECIMAL(18,2)",
        "DECIMAL(18,4)",
        "INTEGER",
        "SMALLINT",
        "TINYINT",
        "VARCHAR",
    }
    for table_name, table in contract()["tables"].items():
        for column_name, definition in table["columns"].items():
            assert set(definition) == {"type", "nullable"}, (
                table_name,
                column_name,
            )
            assert definition["type"] in supported, (table_name, column_name)
            assert isinstance(definition["nullable"], bool)


def test_all_foreign_keys_resolve_to_declared_columns() -> None:
    tables = contract()["tables"]

    for table_name, table in tables.items():
        for foreign_key in table.get("foreign_keys", []):
            target_table, target_columns = parse_reference(foreign_key["references"])
            source_columns = foreign_key["columns"]

            assert target_table in tables
            assert len(source_columns) == len(target_columns)
            assert set(source_columns) <= table["columns"].keys(), table_name
            assert set(target_columns) <= tables[target_table]["columns"].keys()


def test_surrogate_and_business_key_policy_is_explicit() -> None:
    model = contract()
    policy = model["key_policy"]

    assert policy["surrogate_key_type"] == "BIGINT"
    assert policy["deterministic_method"] == (
        "stable_row_number_over_sorted_business_key"
    )
    assert policy["retain_business_keys"] is True
    assert policy["fail_on_unresolved_foreign_key"] is True
    for table_name, table in model["tables"].items():
        key = table["primary_key"][0]
        expected_type = "INTEGER" if table_name == "dim_date" else "BIGINT"
        assert table["columns"][key]["type"] == expected_type


def test_claim_version_scope_prevents_double_counting() -> None:
    policy = contract()["claim_version_policy"]
    claim = contract()["tables"]["fact_claim"]

    assert policy["preserve_all_versions"] is True
    assert policy["exactly_one_current_version"] is True
    assert policy["default_financial_reporting_scope"] == "current_versions_only"
    assert policy["historical_operations_scope"] == "all_versions"
    assert policy["prohibit_cross_version_amount_summing_without_explicit_scope"]
    assert claim["columns"]["is_current_version"] == {
        "type": "BOOLEAN",
        "nullable": False,
    }
    assert "prior_claim_key" in claim["columns"]


def test_financial_semantics_and_date_roles_are_explicit() -> None:
    model = contract()
    measures = model["measure_policy"]
    roles = model["date_roles"]

    assert measures["claim_net_paid_formula"] == (
        "SUM(payment_transaction.signed_transaction_amount)"
    )
    assert measures["claim_line_plan_paid_formula"] == (
        "allowed_amount - member_liability_amount"
    )
    assert measures["denied_claim_positive_net_paid_prohibited"] is True
    assert roles["service_date"] != roles["transaction_date"]
    assert roles["service_date"] != roles["adjudication_date"]
    assert roles["coverage_month"] == "membership_month.coverage_month"


def test_ground_truth_is_separate_evaluation_bridge() -> None:
    model = contract()
    governance = model["governance"]
    anomaly = model["tables"]["bridge_claim_anomaly"]

    assert governance["ground_truth_is_evaluation_only"] is True
    assert governance["prohibit_ground_truth_as_model_feature"] is True
    assert anomaly["grain"] == "one row per controlled anomaly injection"
    assert anomaly["columns"]["evaluation_only"] == {
        "type": "BOOLEAN",
        "nullable": False,
    }
    assert "rule_id" not in model["tables"]["fact_claim"]["columns"]
    assert "expected_financial_exposure" not in model["tables"]["fact_claim"]["columns"]


def test_reconciliation_checks_are_unique_and_complete() -> None:
    checks = contract()["reconciliation_checks"]
    identifiers = [row["check_id"] for row in checks]

    assert len(checks) >= 9
    assert len(identifiers) == len(set(identifiers))
    assert all(identifier.startswith("TRU") for identifier in identifiers)
    assert all(row["expression"] for row in checks)


def test_privacy_determinism_and_storage_controls_are_safe() -> None:
    model = contract()
    dataset = model["dataset"]
    governance = model["governance"]

    assert dataset["output_format"] == "parquet"
    assert dataset["compression"] == "zstd"
    assert dataset["trusted_output_root"].startswith("data/curated/")
    assert dataset["full_output_committed_to_git"] is False
    assert governance["synthetic_records_only"] is True
    assert governance["contains_protected_health_information"] is False
    assert governance["contains_real_member_identifiers"] is False
    assert governance["contains_real_provider_identities"] is False
    assert governance["publishable_samples_are_synthetic_only"] is True
    ignored = subprocess.run(
        ["git", "check-ignore", "data/curated/trusted_claims/fact_claim.parquet"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
