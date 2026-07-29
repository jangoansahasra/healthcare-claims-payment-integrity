from pathlib import Path

import pytest

from src.transformation.physician_silver import (
    PhysicianSilverError,
    load_contract,
    measure_type,
    normalized_measure_expression,
    provider_size_band_expression,
    source_measure_columns,
    suppression_status_expression,
    target_column_name,
    top_coded_indicator_expression,
)

CONTRACT_PATH = Path("config/physician_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(CONTRACT_PATH)


def test_load_contract_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yml"

    with pytest.raises(PhysicianSilverError, match="does not exist"):
        load_contract(missing_path)


def test_source_measure_columns_excludes_dimensions_and_lineage(
    contract: dict,
) -> None:
    source_columns = [
        "Rndrng_NPI",
        "Tot_Benes",
        "Tot_Mdcr_Pymt_Amt",
        "Drug_Sprsn_Ind",
        "_source_id",
    ]

    assert source_measure_columns(source_columns, contract) == [
        "Tot_Benes",
        "Tot_Mdcr_Pymt_Amt",
    ]


def test_target_column_name_normalizes_cms_names() -> None:
    assert target_column_name("Tot_Mdcr_Pymt_Amt") == "tot_mdcr_pymt_amt"
    assert target_column_name("Bene_Avg_Risk_Scre") == "bene_avg_risk_scre"


def test_measure_type_uses_governed_integer_columns(contract: dict) -> None:
    assert measure_type("Tot_Benes", contract) == "BIGINT"
    assert measure_type("Bene_Feml_Cnt", contract) == "BIGINT"
    assert measure_type("Tot_Mdcr_Pymt_Amt", contract) == "DECIMAL(38, 6)"


def test_normalized_measure_expression_casts_without_zero_imputation(
    contract: dict,
) -> None:
    expression = normalized_measure_expression(
        "Tot_Mdcr_Pymt_Amt",
        contract,
    )

    assert 'TRY_CAST(TRIM("Tot_Mdcr_Pymt_Amt")' in expression
    assert "DECIMAL(38, 6)" in expression
    assert 'AS "tot_mdcr_pymt_amt"' in expression
    assert "COALESCE" not in expression


def test_suppression_status_expression_preserves_both_tokens(
    contract: dict,
) -> None:
    expression = suppression_status_expression(
        "Drug_Sprsn_Ind",
        contract,
    )

    assert "WHEN \"Drug_Sprsn_Ind\" = '*' THEN" in expression
    assert "'primary_suppressed_fewer_than_11'" in expression
    assert "WHEN \"Drug_Sprsn_Ind\" = '#' THEN" in expression
    assert "'counter_suppressed'" in expression
    assert "ELSE 'not_suppressed'" in expression


def test_medical_suppression_uses_semantic_group_name(
    contract: dict,
) -> None:
    expression = suppression_status_expression(
        "Med_Sprsn_Ind",
        contract,
    )

    assert 'AS "medical_suppression_status"' in expression
    assert "med_suppression_status" not in expression


def test_top_coded_indicator_marks_only_upper_bound(
    contract: dict,
) -> None:
    expression = top_coded_indicator_expression(
        "Bene_CC_PH_Diabetes_V2_Pct",
        contract,
    )

    assert 'TRY_CAST(TRIM("Bene_CC_PH_Diabetes_V2_Pct")' in expression
    assert "= 75" in expression
    assert 'AS "bene_cc_ph_diabetes_v2_pct_is_top_coded"' in expression


def test_provider_size_band_expression_uses_governed_boundaries(
    contract: dict,
) -> None:
    expression = provider_size_band_expression(contract)

    assert "BETWEEN 11 AND 49 THEN 'small'" in expression
    assert "BETWEEN 50 AND 199 THEN 'medium'" in expression
    assert "BETWEEN 200 AND 999 THEN 'large'" in expression
    assert ">= 1000 THEN 'very_large'" in expression
    assert "ELSE NULL END AS provider_size_band" in expression
