from pathlib import Path

import pytest

from src.transformation.outpatient_silver import (
    OutpatientSilverError,
    load_contract,
    measure_type,
    missing_dimension_indicator_expression,
    normalized_measure_expression,
    service_volume_band_expression,
    source_measure_columns,
    suppression_status_expression,
    target_column_name,
)

CONTRACT_PATH = Path("config/outpatient_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(CONTRACT_PATH)


def test_load_contract_requires_mapping(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(OutpatientSilverError, match="must contain a mapping"):
        load_contract(path)


def test_source_measure_columns_returns_seven_measures(contract: dict) -> None:
    columns = [
        *contract["source_dimensions"],
        *contract["numeric_typing"]["integer_columns"],
        *contract["numeric_typing"]["decimal_columns"],
    ]
    assert len(source_measure_columns(columns, contract)) == 7


def test_target_names_and_types_are_semantic(contract: dict) -> None:
    assert target_column_name("CAPC_Srvcs") == "comprehensive_apc_services"
    assert target_column_name("Avg_Mdcr_Alowd_Amt") == "average_medicare_allowed_amount"
    assert measure_type("Bene_Cnt", contract) == "BIGINT"
    assert measure_type("Avg_Mdcr_Pymt_Amt", contract) == "DECIMAL(38, 6)"


def test_measure_expression_preserves_nulls(contract: dict) -> None:
    expression = normalized_measure_expression("CAPC_Srvcs", contract)
    assert "TRY_CAST" in expression
    assert 'AS "comprehensive_apc_services"' in expression
    assert "COALESCE" not in expression


def test_missing_ruca_indicator_is_explicit(contract: dict) -> None:
    expression = missing_dimension_indicator_expression(
        "Rndrng_Prvdr_RUCA", "hospital_ruca_code", contract
    )
    assert '"Rndrng_Prvdr_RUCA" IS NULL' in expression
    assert 'AS "hospital_ruca_code_is_missing"' in expression


@pytest.mark.parametrize(
    ("group", "measure"),
    [
        ("provider_apc_summary", "comprehensive_apc_services"),
        ("beneficiary_count", "beneficiary_count"),
        ("outlier_detail", "outlier_services"),
    ],
)
def test_suppression_status_is_explicit(
    group: str, measure: str, contract: dict
) -> None:
    expression = suppression_status_expression(group, contract)
    assert f'"{measure}" IS NULL' in expression
    assert "'suppressed'" in expression
    assert "'published'" in expression


def test_unknown_suppression_group_fails(contract: dict) -> None:
    with pytest.raises(OutpatientSilverError, match="Unknown suppression group"):
        suppression_status_expression("unknown", contract)


def test_service_volume_band_handles_suppression(contract: dict) -> None:
    expression = service_volume_band_expression(contract)
    assert '"comprehensive_apc_services" IS NULL' in expression
    assert "'suppressed'" in expression
    assert '"comprehensive_apc_services" BETWEEN 11 AND 20' in expression
    assert '"comprehensive_apc_services" >= 89' in expression
