from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from src.transformation.build_physician_service_silver import (
    build_physician_service_silver,
)
from src.transformation.geographic_silver import sql_literal
from src.transformation.physician_service_silver import PhysicianServiceSilverError

ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT = ROOT / "config" / "physician_service_silver.yml"


def create_contract(tmp_path: Path) -> Path:
    contract = yaml.safe_load(BASE_CONTRACT.read_text(encoding="utf-8"))
    contract["paths"] = {
        "bronze_glob": str(tmp_path / "bronze.parquet"),
        "silver_output": str(tmp_path / "silver.parquet"),
        "quality_report": str(tmp_path / "quality.json"),
    }
    contract["numeric_typing"]["observed_fractional_service_rows"] = 1
    contract["nullable_dimension_policy"]["provider_state_fips"][
        "observed_null_or_blank_rows"
    ] = 0
    contract["nullable_dimension_policy"]["provider_ruca_code"][
        "observed_null_or_blank_rows"
    ] = 0
    path = tmp_path / "contract.yml"
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    return path


def create_bronze(path: Path, invalid_payment: bool = False) -> None:
    rows = []
    for index, year in enumerate(range(2019, 2025)):
        allowed = 80 + index
        payment = allowed - 10
        if invalid_payment and year == 2024:
            payment = allowed + 1
        rows.append(
            {
                "Rndrng_NPI": f"100000000{index}",
                "Rndrng_Prvdr_Last_Org_Name": f"Provider {index}",
                "Rndrng_Prvdr_First_Name": "Test",
                "Rndrng_Prvdr_MI": None,
                "Rndrng_Prvdr_Crdntls": "MD",
                "Rndrng_Prvdr_Ent_Cd": "I",
                "Rndrng_Prvdr_St1": "1 Main Street",
                "Rndrng_Prvdr_St2": None,
                "Rndrng_Prvdr_City": "Baltimore",
                "Rndrng_Prvdr_State_Abrvtn": "MD",
                "Rndrng_Prvdr_State_FIPS": "24",
                "Rndrng_Prvdr_Zip5": "21201",
                "Rndrng_Prvdr_RUCA": "1",
                "Rndrng_Prvdr_RUCA_Desc": "Metro",
                "Rndrng_Prvdr_Cntry": "CA" if year == 2020 else "US",
                "Rndrng_Prvdr_Type": "Internal Medicine",
                "Rndrng_Prvdr_Mdcr_Prtcptg_Ind": "Y",
                "HCPCS_Cd": f"99{210 + index}",
                "HCPCS_Desc": "Office visit",
                "HCPCS_Drug_Ind": "N",
                "Place_Of_Srvc": "O",
                "Tot_Benes": str([11, 18, 32, 73, 100, 200][index]),
                "Tot_Srvcs": "12.5" if year == 2019 else "20",
                "Tot_Bene_Day_Srvcs": "11",
                "Avg_Sbmtd_Chrg": "100",
                "Avg_Mdcr_Alowd_Amt": str(allowed),
                "Avg_Mdcr_Pymt_Amt": str(payment),
                "Avg_Mdcr_Stdzd_Amt": "90",
                "_source_id": "cms_physician_provider_service",
                "_reporting_year": year,
                "_source_file": f"physician_{year}.csv",
                "_acquired_at_utc": "2026-08-01T00:00:00+00:00",
            }
        )
    with duckdb.connect() as connection:
        connection.register("fixture", pd.DataFrame(rows))
        connection.execute(
            f"COPY fixture TO {sql_literal(str(path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )


def test_build_end_to_end(tmp_path: Path) -> None:
    contract_path = create_contract(tmp_path)
    create_bronze(tmp_path / "bronze.parquet")
    report = build_physician_service_silver(contract_path)
    assert report["bronze_row_count"] == report["silver_row_count"] == 6
    assert report["measure_count"] == 7
    assert report["fractional_total_service_count"] == 1
    assert report["all_checks_passed"] is True
    with duckdb.connect() as connection:
        schema = {
            row[0]: row[1]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)",
                [str(tmp_path / "silver.parquet")],
            ).fetchall()
        }
        rows = connection.execute(
            """SELECT reporting_year, beneficiary_volume_band,
            provider_geography_scope, peer_state_fips
            FROM read_parquet(?) ORDER BY 1""",
            [str(tmp_path / "silver.parquet")],
        ).fetchall()
    assert schema["rendering_npi"] == "VARCHAR"
    assert schema["total_beneficiaries"] == "BIGINT"
    assert schema["total_services"] == "DECIMAL(38,6)"
    assert [row[1] for row in rows[:4]] == ["low", "medium", "high", "very_high"]
    assert rows[1][2:] == ("Foreign", "Not applicable")


def test_build_rejects_payment_above_allowed(tmp_path: Path) -> None:
    contract_path = create_contract(tmp_path)
    create_bronze(tmp_path / "bronze.parquet", invalid_payment=True)
    with pytest.raises(PhysicianServiceSilverError, match="quality checks failed"):
        build_physician_service_silver(contract_path)
