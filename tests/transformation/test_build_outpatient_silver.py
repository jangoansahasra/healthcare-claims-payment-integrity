from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from src.transformation.build_outpatient_silver import build_outpatient_silver
from src.transformation.geographic_silver import sql_literal
from src.transformation.outpatient_silver import OutpatientSilverError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT_PATH = PROJECT_ROOT / "config" / "outpatient_silver.yml"


def create_fixture_contract(tmp_path: Path) -> Path:
    contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["paths"] = {
        "bronze_glob": str(tmp_path / "bronze.parquet"),
        "silver_output": str(tmp_path / "silver.parquet"),
        "quality_report": str(tmp_path / "quality.json"),
    }
    contract["suppression_semantics"]["provider_apc_summary"][
        "observed_suppressed_rows"
    ] = 1
    contract["suppression_semantics"]["beneficiary_count"][
        "observed_additional_suppressed_rows"
    ] = 1
    contract["suppression_semantics"]["outlier_detail"]["observed_suppressed_rows"] = 2
    path = tmp_path / "contract.yml"
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")
    return path


def create_bronze_fixture(path: Path, *, invalid_payment: bool = False) -> None:
    rows = []
    for index, year in enumerate((2019, 2021, 2023)):
        summary_suppressed = year == 2019
        beneficiary_suppressed = year != 2023
        outlier_suppressed = year != 2023
        allowed = 80 + index
        payment = allowed - 10
        if invalid_payment and year == 2023:
            payment = allowed + 1
        rows.append(
            {
                "Rndrng_Prvdr_CCN": f"10000{index}",
                "Rndrng_Prvdr_Org_Name": f"Hospital {index}",
                "Rndrng_Prvdr_St": f"{index} Main Street",
                "Rndrng_Prvdr_City": "Baltimore",
                "Rndrng_Prvdr_State_Abrvtn": "MD",
                "Rndrng_Prvdr_State_FIPS": "24",
                "Rndrng_Prvdr_Zip5": "21201",
                "Rndrng_Prvdr_RUCA": None if year == 2021 else "1",
                "Rndrng_Prvdr_RUCA_Desc": None if year == 2021 else "Metropolitan",
                "APC_Cd": f"{5000 + index:04d}",
                "APC_Desc": f"APC {index}",
                "Bene_Cnt": None if beneficiary_suppressed else "25",
                "CAPC_Srvcs": None if summary_suppressed else str((25, 100)[index - 1]),
                "Avg_Tot_Sbmtd_Chrgs": None if summary_suppressed else "100",
                "Avg_Mdcr_Alowd_Amt": None if summary_suppressed else str(allowed),
                "Avg_Mdcr_Pymt_Amt": None if summary_suppressed else str(payment),
                "Outlier_Srvcs": None if outlier_suppressed else "11",
                "Avg_Mdcr_Outlier_Amt": None if outlier_suppressed else "150",
                "_source_id": "cms_outpatient_provider_service",
                "_reporting_year": year,
                "_source_file": f"outpatient_{year}.csv",
                "_acquired_at_utc": "2026-07-31T00:00:00+00:00",
            }
        )
    with duckdb.connect() as connection:
        connection.register("fixture", pd.DataFrame(rows))
        connection.execute(
            f"COPY fixture TO {sql_literal(str(path))} "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )


def test_build_outpatient_silver_end_to_end(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    create_bronze_fixture(tmp_path / "bronze.parquet")
    report = build_outpatient_silver(contract_path)
    assert report["bronze_row_count"] == report["silver_row_count"] == 3
    assert report["measure_count"] == 7
    assert report["reporting_periods"] == [2019, 2021, 2023]
    assert report["suppression_counts"] == {
        "provider_apc_summary": 1,
        "beneficiary_count": 2,
        "outlier_detail": 2,
    }
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
            """SELECT reporting_period, provider_apc_summary_status,
            beneficiary_count_status, outlier_detail_status,
            service_volume_band, hospital_ruca_code_is_missing
            FROM read_parquet(?) ORDER BY 1""",
            [str(tmp_path / "silver.parquet")],
        ).fetchall()
    assert schema["hospital_ccn"] == "VARCHAR"
    assert schema["comprehensive_apc_code"] == "VARCHAR"
    assert schema["beneficiary_count"] == "BIGINT"
    assert schema["average_medicare_payment"] == "DECIMAL(38,6)"
    assert rows[0][1:5] == ("suppressed", "suppressed", "suppressed", "suppressed")
    assert rows[1][-1] is True


def test_build_rejects_medicare_payment_above_allowed(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    create_bronze_fixture(tmp_path / "bronze.parquet", invalid_payment=True)
    with pytest.raises(OutpatientSilverError, match="quality checks failed"):
        build_outpatient_silver(contract_path)
