from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from src.transformation.build_inpatient_silver import build_inpatient_silver
from src.transformation.geographic_silver import sql_literal
from src.transformation.inpatient_silver import InpatientSilverError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT_PATH = PROJECT_ROOT / "config" / "inpatient_silver.yml"


def create_fixture_contract(tmp_path: Path) -> Path:
    contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["paths"] = {
        "bronze_glob": str(tmp_path / "bronze.parquet"),
        "silver_output": str(tmp_path / "silver.parquet"),
        "quality_report": str(tmp_path / "quality.json"),
    }
    path = tmp_path / "contract.yml"
    path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    return path


def create_bronze_fixture(
    path: Path,
    *,
    invalid_numeric: bool = False,
    invalid_payment_relationship: bool = False,
) -> None:
    rows = []
    for index, year in enumerate(range(2019, 2025)):
        total_payment = 12000 + index
        medicare_payment = 10000 + index
        covered_charge = 30000 + index

        if year == 2020:
            covered_charge = 5000
        if invalid_payment_relationship and year == 2024:
            medicare_payment = total_payment + 1

        discharges = str([11, 14, 21, 36, 50, 100][index])
        if invalid_numeric and year == 2024:
            discharges = "not-a-number"

        rows.append(
            {
                "Rndrng_Prvdr_CCN": f"10000{index}",
                "Rndrng_Prvdr_Org_Name": f"Hospital {index}",
                "Rndrng_Prvdr_City": "Baltimore",
                "Rndrng_Prvdr_St": f"{index} Main Street",
                "Rndrng_Prvdr_State_FIPS": "24",
                "Rndrng_Prvdr_Zip5": "21201",
                "Rndrng_Prvdr_State_Abrvtn": "MD",
                "Rndrng_Prvdr_RUCA": None if year == 2021 else "1",
                "Rndrng_Prvdr_RUCA_Desc": (None if year == 2021 else "Metropolitan"),
                "DRG_Cd": f"{470 + index:03d}",
                "DRG_Desc": f"DRG {470 + index}",
                "Tot_Dschrgs": discharges,
                "Avg_Submtd_Cvrd_Chrg": str(covered_charge),
                "Avg_Tot_Pymt_Amt": str(total_payment),
                "Avg_Mdcr_Pymt_Amt": str(medicare_payment),
                "_source_id": "cms_inpatient_provider_service",
                "_reporting_year": year,
                "_source_file": f"inpatient_{year}.csv",
                "_acquired_at_utc": "2026-07-30T00:00:00+00:00",
            }
        )

    with duckdb.connect() as connection:
        connection.register("fixture", pd.DataFrame(rows))
        connection.execute(
            f"""
            COPY fixture TO {sql_literal(str(path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )


def test_build_inpatient_silver_end_to_end(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    silver_path = tmp_path / "silver.parquet"
    quality_path = tmp_path / "quality.json"
    create_bronze_fixture(bronze_path)

    report = build_inpatient_silver(contract_path)

    assert silver_path.exists()
    assert quality_path.exists()
    assert report["bronze_row_count"] == 6
    assert report["silver_row_count"] == 6
    assert report["measure_count"] == 4
    assert report["reporting_years"] == list(range(2019, 2025))
    assert report["total_payment_above_covered_charge_count"] == 1
    assert report["all_checks_passed"] is True

    with duckdb.connect() as connection:
        schema = {
            row[0]: row[1]
            for row in connection.execute(
                "DESCRIBE SELECT * FROM read_parquet(?)",
                [str(silver_path)],
            ).fetchall()
        }
        rows = connection.execute(
            """
            SELECT
                reporting_year,
                discharge_volume_band,
                hospital_ruca_code,
                hospital_ruca_code_is_missing,
                total_payment_above_covered_charge
            FROM read_parquet(?)
            ORDER BY reporting_year
            """,
            [str(silver_path)],
        ).fetchall()

    assert schema["hospital_ccn"] == "VARCHAR"
    assert schema["ms_drg_code"] == "VARCHAR"
    assert schema["reporting_year"] == "INTEGER"
    assert schema["total_discharges"] == "BIGINT"
    assert schema["average_total_payment"] == "DECIMAL(38,6)"
    assert [row[1] for row in rows[:4]] == [
        "low",
        "medium",
        "high",
        "very_high",
    ]
    assert rows[1][-1] is True
    assert rows[2][2:4] == ("Unknown", True)


def test_build_rejects_unparseable_numeric_value(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    create_bronze_fixture(
        tmp_path / "bronze.parquet",
        invalid_numeric=True,
    )

    with pytest.raises(InpatientSilverError, match="Unparseable numeric"):
        build_inpatient_silver(contract_path)


def test_build_rejects_medicare_payment_above_total(
    tmp_path: Path,
) -> None:
    contract_path = create_fixture_contract(tmp_path)
    create_bronze_fixture(
        tmp_path / "bronze.parquet",
        invalid_payment_relationship=True,
    )

    with pytest.raises(
        InpatientSilverError,
        match="quality checks failed",
    ):
        build_inpatient_silver(contract_path)
