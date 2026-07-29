from pathlib import Path

import pytest

from src.transformation.part_d_silver import (
    PartDSilverError,
    load_contract,
    measure_type,
    missing_dimension_indicator_expression,
    normalized_dimension_expression,
    normalized_measure_expression,
    prescriber_size_band_expression,
    source_measure_columns,
    suppression_status_expression,
    target_column_name,
)

CONTRACT_PATH = Path("config/part_d_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(CONTRACT_PATH)


def test_load_contract_rejects_missing_file(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.yml"

    with pytest.raises(
        PartDSilverError,
        match="does not exist",
    ):
        load_contract(missing)


def test_source_measure_columns_excludes_dimensions_flags_and_lineage(
    contract: dict,
) -> None:
    columns = [
        "Prscrbr_NPI",
        "Tot_Clms",
        "Tot_Drug_Cst",
        "GE65_Sprsn_Flag",
        "_source_id",
    ]

    assert source_measure_columns(columns, contract) == [
        "Tot_Clms",
        "Tot_Drug_Cst",
    ]


def test_target_column_name_normalizes_cms_names() -> None:
    assert target_column_name("Tot_Drug_Cst") == "tot_drug_cst"
    assert target_column_name("Opioid_LA_Prscrbr_Rate") == "opioid_la_prscrbr_rate"


def test_measure_type_uses_governed_classes(
    contract: dict,
) -> None:
    assert measure_type("Tot_Clms", contract) == "BIGINT"
    assert measure_type("Bene_Dual_Cnt", contract) == "BIGINT"
    assert measure_type("Tot_30day_Fills", contract) == "DECIMAL(38, 6)"
    assert measure_type("Tot_Drug_Cst", contract) == "DECIMAL(38, 6)"


def test_normalized_measure_expression_preserves_nulls(
    contract: dict,
) -> None:
    expression = normalized_measure_expression(
        "Tot_Drug_Cst",
        contract,
    )

    assert 'TRY_CAST(TRIM(CAST("Tot_Drug_Cst" AS VARCHAR))' in expression
    assert "DECIMAL(38, 6)" in expression
    assert 'AS "tot_drug_cst"' in expression
    assert "COALESCE" not in expression


def test_nullable_dimension_uses_explicit_unknown_bucket(
    contract: dict,
) -> None:
    expression = normalized_dimension_expression(
        "Prscrbr_Type",
        "prescriber_type",
        contract,
    )

    assert "COALESCE" in expression
    assert "'Unknown'" in expression
    assert 'AS "prescriber_type"' in expression


def test_nonnullable_dimension_is_trimmed_without_unknown_bucket(
    contract: dict,
) -> None:
    expression = normalized_dimension_expression(
        "Prscrbr_Cntry",
        "prescriber_country_code",
        contract,
    )

    assert "NULLIF(TRIM" in expression
    assert "COALESCE" not in expression
    assert 'AS "prescriber_country_code"' in expression


def test_missing_dimension_indicator_preserves_lineage(
    contract: dict,
) -> None:
    expression = missing_dimension_indicator_expression(
        "Prscrbr_RUCA",
        "prescriber_ruca_code",
        contract,
    )

    assert '"Prscrbr_RUCA" IS NULL' in expression
    assert "TRIM" in expression
    assert 'AS "prescriber_ruca_code_is_missing"' in expression


def test_suppression_status_uses_semantic_group_name(
    contract: dict,
) -> None:
    expression = suppression_status_expression(
        "GE65_Sprsn_Flag",
        contract,
    )

    assert "WHEN TRIM(CAST(\"GE65_Sprsn_Flag\" AS VARCHAR)) = '*'" in expression
    assert "'primary_suppressed'" in expression
    assert "WHEN TRIM(CAST(\"GE65_Sprsn_Flag\" AS VARCHAR)) = '#'" in expression
    assert "'counter_suppressed'" in expression
    assert "ELSE 'not_suppressed'" in expression
    assert 'AS "age_65_and_older_activity_suppression_status"' in expression


def test_prescriber_size_bands_use_observed_quartiles(
    contract: dict,
) -> None:
    expression = prescriber_size_band_expression(contract)

    assert "BETWEEN 11 AND 55 THEN 'small'" in expression
    assert "BETWEEN 56 AND 200 THEN 'medium'" in expression
    assert "BETWEEN 201 AND 938 THEN 'large'" in expression
    assert ">= 939 THEN 'very_large'" in expression
    assert "ELSE NULL END AS prescriber_size_band" in expression
