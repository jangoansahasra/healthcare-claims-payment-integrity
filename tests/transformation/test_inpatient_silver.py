from pathlib import Path

import pytest

from src.transformation.inpatient_silver import (
    InpatientSilverError,
    discharge_volume_band_expression,
    load_contract,
    measure_type,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    source_measure_columns,
    target_column_name,
    total_payment_above_charge_expression,
)

CONTRACT_PATH = Path("config/inpatient_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(CONTRACT_PATH)


def test_load_contract_requires_mapping(tmp_path: Path) -> None:
    path = tmp_path / "invalid.yml"
    path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(InpatientSilverError, match="must contain a mapping"):
        load_contract(path)


def test_source_measure_columns_returns_four_governed_measures(
    contract: dict,
) -> None:
    source_columns = [
        *contract["source_dimensions"],
        "Tot_Dschrgs",
        "Avg_Submtd_Cvrd_Chrg",
        "Avg_Tot_Pymt_Amt",
        "Avg_Mdcr_Pymt_Amt",
        *contract["retained_lineage"],
    ]

    assert source_measure_columns(source_columns, contract) == [
        "Tot_Dschrgs",
        "Avg_Submtd_Cvrd_Chrg",
        "Avg_Tot_Pymt_Amt",
        "Avg_Mdcr_Pymt_Amt",
    ]


def test_target_column_names_are_semantic() -> None:
    assert target_column_name("Tot_Dschrgs") == "total_discharges"
    assert target_column_name("Avg_Submtd_Cvrd_Chrg") == (
        "average_submitted_covered_charge"
    )
    assert target_column_name("Avg_Tot_Pymt_Amt") == "average_total_payment"
    assert target_column_name("Avg_Mdcr_Pymt_Amt") == ("average_medicare_payment")


def test_measure_types_follow_contract(contract: dict) -> None:
    assert measure_type("Tot_Dschrgs", contract) == "BIGINT"
    assert measure_type("Avg_Tot_Pymt_Amt", contract) == "DECIMAL(38, 6)"

    with pytest.raises(InpatientSilverError, match="no governed type"):
        measure_type("Unknown_Measure", contract)


def test_normalized_measure_expression_is_string_safe(
    contract: dict,
) -> None:
    expression = normalized_measure_expression(
        "Avg_Tot_Pymt_Amt",
        contract,
    )

    assert 'TRIM(CAST("Avg_Tot_Pymt_Amt" AS VARCHAR))' in expression
    assert "DECIMAL(38, 6)" in expression
    assert 'AS "average_total_payment"' in expression
    assert "COALESCE" not in expression


def test_nullable_ruca_dimension_uses_unknown_bucket(
    contract: dict,
) -> None:
    expression = normalized_dimension_expression(
        "Rndrng_Prvdr_RUCA",
        "hospital_ruca_code",
        contract,
    )

    assert "NULLIF(TRIM" in expression
    assert "COALESCE" in expression
    assert "'Unknown'" in expression
    assert 'AS "hospital_ruca_code"' in expression


def test_nonnullable_dimension_is_not_imputed(contract: dict) -> None:
    expression = normalized_dimension_expression(
        "Rndrng_Prvdr_CCN",
        "hospital_ccn",
        contract,
    )

    assert "NULLIF(TRIM" in expression
    assert "COALESCE" not in expression


def test_missing_dimension_indicator_preserves_source_null(
    contract: dict,
) -> None:
    expression = missing_dimension_indicator_expression(
        "Rndrng_Prvdr_RUCA",
        "hospital_ruca_code",
        contract,
    )

    assert '"Rndrng_Prvdr_RUCA" IS NULL' in expression
    assert 'AS "hospital_ruca_code_is_missing"' in expression


def test_discharge_volume_band_expression_is_contract_driven(
    contract: dict,
) -> None:
    expression = discharge_volume_band_expression(contract)

    assert '"total_discharges" BETWEEN 11 AND 13' in expression
    assert '"total_discharges" BETWEEN 14 AND 20' in expression
    assert '"total_discharges" BETWEEN 21 AND 35' in expression
    assert '"total_discharges" >= 36' in expression
    assert "AS discharge_volume_band" in expression


def test_total_payment_above_charge_is_observation_not_rejection() -> None:
    expression = total_payment_above_charge_expression()

    assert '"average_total_payment" >' in expression
    assert '"average_submitted_covered_charge"' in expression
    assert "THEN TRUE ELSE FALSE" in expression
    assert "AS total_payment_above_covered_charge" in expression
