from pathlib import Path

import pytest

from src.transformation.geographic_silver import (
    SilverTransformationError,
    geography_identifier_expression,
    invalid_numeric_predicate,
    load_contract,
    measure_type,
    normalized_measure_expression,
    quote_identifier,
    source_measure_columns,
    sql_literal,
    target_measure_name,
)

CONTRACT_PATH = Path("config/geographic_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(CONTRACT_PATH)


def test_load_contract_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yml"

    with pytest.raises(SilverTransformationError, match="does not exist"):
        load_contract(missing_path)


def test_sql_quoting_escapes_special_characters() -> None:
    assert quote_identifier('example"name') == '"example""name"'
    assert sql_literal("example's") == "'example''s'"


def test_source_measure_columns_excludes_dimensions_and_lineage(
    contract: dict,
) -> None:
    source_columns = [
        "YEAR",
        "BENE_GEO_LVL",
        "TOT_MDCR_PYMT_AMT",
        "BENES_TOTAL_CNT",
        "_source_id",
    ]

    assert source_measure_columns(source_columns, contract) == [
        "TOT_MDCR_PYMT_AMT",
        "BENES_TOTAL_CNT",
    ]


def test_measure_names_and_types_are_normalized(contract: dict) -> None:
    assert target_measure_name("TOT_MDCR_PYMT_AMT") == "tot_mdcr_pymt_amt"
    assert measure_type("BENES_TOTAL_CNT", contract) == "BIGINT"
    assert measure_type("TOT_MDCR_PYMT_AMT", contract) == "DECIMAL(38, 6)"


def test_normalized_measure_expression_preserves_special_values(
    contract: dict,
) -> None:
    expression = normalized_measure_expression(
        "TOT_MDCR_PYMT_AMT",
        contract,
    )

    assert "TRIM(\"TOT_MDCR_PYMT_AMT\") IN ('*', '', 'NA')" in expression
    assert "THEN NULL" in expression
    assert "TRY_CAST" in expression
    assert 'AS "tot_mdcr_pymt_amt"' in expression


def test_geography_identifier_expression_handles_aggregates_and_codes(
    contract: dict,
) -> None:
    expression = geography_identifier_expression(contract)

    assert "THEN 'US'" in expression
    assert "THEN 'AGG_TERRITORY'" in expression
    assert "THEN 'AGG_ZZ'" in expression
    assert "UPPER(BENE_GEO_LVL) || ':' || BENE_GEO_CD" in expression
    assert "ELSE NULL END AS geography_id" in expression


def test_invalid_numeric_predicate_excludes_governed_tokens(
    contract: dict,
) -> None:
    predicate = invalid_numeric_predicate("BENES_TOTAL_CNT", contract)

    assert "TRIM(\"BENES_TOTAL_CNT\") NOT IN ('*', '', 'NA')" in predicate
    assert "AS BIGINT" in predicate
    assert "IS NULL" in predicate
