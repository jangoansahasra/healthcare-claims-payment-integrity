from pathlib import Path

import pytest

from src.transformation.physician_service_silver import (
    PhysicianServiceSilverError,
    beneficiary_volume_band_expression,
    load_contract,
    measure_type,
    missing_dimension_indicator_expression,
    normalized_measure_expression,
    source_measure_columns,
    target_column_name,
)

PATH = Path("config/physician_service_silver.yml")


@pytest.fixture
def contract() -> dict:
    return load_contract(PATH)


def test_load_requires_mapping(tmp_path: Path) -> None:
    path = tmp_path / "bad.yml"
    path.write_text("- bad\n", encoding="utf-8")
    with pytest.raises(PhysicianServiceSilverError, match="must contain a mapping"):
        load_contract(path)


def test_seven_measures_are_governed(contract: dict) -> None:
    columns = [
        "Tot_Benes",
        "Tot_Srvcs",
        "Tot_Bene_Day_Srvcs",
        "Avg_Sbmtd_Chrg",
        "Avg_Mdcr_Alowd_Amt",
        "Avg_Mdcr_Pymt_Amt",
        "Avg_Mdcr_Stdzd_Amt",
    ]
    assert source_measure_columns(columns, contract) == columns


def test_total_services_is_decimal(contract: dict) -> None:
    assert target_column_name("Tot_Srvcs") == "total_services"
    assert measure_type("Tot_Srvcs", contract) == "DECIMAL(38, 6)"
    expression = normalized_measure_expression("Tot_Srvcs", contract)
    assert "DECIMAL(38, 6)" in expression
    assert 'AS "total_services"' in expression


def test_missing_geography_indicator(contract: dict) -> None:
    expression = missing_dimension_indicator_expression(
        "Rndrng_Prvdr_RUCA", "provider_ruca_code", contract
    )
    assert '"Rndrng_Prvdr_RUCA" IS NULL' in expression
    assert 'AS "provider_ruca_code_is_missing"' in expression


def test_beneficiary_bands_are_contract_driven(contract: dict) -> None:
    expression = beneficiary_volume_band_expression(contract)
    assert '"total_beneficiaries" BETWEEN 11 AND 17' in expression
    assert '"total_beneficiaries" BETWEEN 18 AND 31' in expression
    assert '"total_beneficiaries" >= 73' in expression
