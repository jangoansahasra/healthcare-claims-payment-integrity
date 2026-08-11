from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/bi_semantic_contract.yml"


def load_contract() -> dict:
    return yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_metric_dictionary_is_complete_and_unique() -> None:
    metrics = load_contract()["metrics"]
    required = {
        "display_name",
        "source_table",
        "grain",
        "formula",
        "format",
        "date_role",
    }
    assert list(metrics) == [f"BI{number:03d}" for number in range(1, 15)]
    assert len({metric["display_name"] for metric in metrics.values()}) == len(metrics)
    assert all(required <= set(metric) for metric in metrics.values())


def test_relationships_are_unambiguous_and_governed() -> None:
    model = load_contract()["semantic_model"]
    relationships = model["relationships"]
    assert model["many_to_many_relationships_allowed"] is False
    assert model["ambiguous_relationships_allowed"] is False
    assert all(item["cardinality"] == "many_to_one" for item in relationships)
    assert all(item["filter_direction"] == "single" for item in relationships)


def test_tolerances_and_denominators_are_explicit() -> None:
    contract = load_contract()
    assert contract["tolerances"]["financial_usd"] == 0.01
    assert contract["tolerances"]["count"] == 0
    for metric_id in ("BI003", "BI004", "BI005", "BI006"):
        assert "eligible_member_months" in contract["metrics"][metric_id]["formula"]


def test_date_roles_and_privacy_are_explicit() -> None:
    contract = load_contract()
    assert contract["metrics"]["BI001"]["date_role"] == "service_month"
    assert contract["metrics"]["BI007"]["date_role"] == "payment_month"
    assert (
        contract["governance"][
            "service_and_payment_date_roles_must_be_visibly_distinct"
        ]
        is True
    )
    assert contract["privacy"]["threshold"] == 11
    assert (
        contract["privacy"]["suppressed_values_may_not_contribute_to_tooltips"] is True
    )


def test_evaluation_ground_truth_is_excluded() -> None:
    contract = load_contract()
    sources = {metric["source_table"] for metric in contract["metrics"].values()}
    assert (
        contract["governance"]["ordinary_features_may_access_evaluation_ground_truth"]
        is False
    )
    assert all(not source.startswith("evaluation.") for source in sources)


def test_looker_studio_has_exactly_six_governed_pages() -> None:
    looker = load_contract()["looker_studio"]
    assert [page["page_id"] for page in looker["pages"]] == [
        f"LS{number:02d}" for number in range(1, 7)
    ]
    assert all(page["metric_ids"] for page in looker["pages"])
    assert looker["completion_status"] == "not_built"


def test_power_bi_validation_scope_is_explicit() -> None:
    contract = load_contract()
    power_bi = contract["power_bi"]
    assert power_bi["connection"] == "Fabric Lakehouse SQL analytics endpoint"
    assert set(power_bi["selected_metric_ids"]) <= set(contract["metrics"])
    assert power_bi["validation_requires_financial_tolerance_usd"] == 0.01
    assert power_bi["completion_status"] == "not_built"


def test_evidence_is_sanitized_and_outputs_are_local() -> None:
    contract = load_contract()
    evidence = contract["evidence"]
    assert {"user_email", "tenant_id", "subscription_id", "pipeline_run_id"} <= set(
        evidence["prohibited_screenshot_fields"]
    )
    assert evidence["screenshots_committed_to_git"] is False
    assert contract["dataset"]["full_output_committed_to_git"] is False


def test_quality_check_identifiers_are_complete() -> None:
    checks = load_contract()["quality_checks"]
    assert [check["check_id"] for check in checks] == [
        f"BIQ{number:03d}" for number in range(1, 13)
    ]
