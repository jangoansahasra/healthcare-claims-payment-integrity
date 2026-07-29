from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from src.transformation.build_physician_silver import (
    build_physician_silver,
)
from src.transformation.geographic_silver import sql_literal
from src.transformation.physician_silver import PhysicianSilverError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT_PATH = PROJECT_ROOT / "config" / "physician_silver.yml"


def create_fixture_contract(tmp_path: Path) -> Path:
    contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["paths"] = {
        "bronze_glob": str(tmp_path / "bronze.parquet"),
        "silver_output": str(tmp_path / "silver.parquet"),
        "suppression_output": str(tmp_path / "suppressions.parquet"),
        "quality_report": str(tmp_path / "quality_report.json"),
    }

    contract_path = tmp_path / "contract.yml"
    contract_path.write_text(
        yaml.safe_dump(contract, sort_keys=False),
        encoding="utf-8",
    )
    return contract_path


def create_bronze_fixture(
    path: Path,
    *,
    invalid_numeric_value: bool = False,
) -> None:
    rows: list[dict] = []

    for index, year in enumerate(range(2019, 2025)):
        drug_indicator = None
        medical_indicator = None

        drug_values = {
            "Drug_Tot_HCPCS_Cds": str(20 + index),
            "Drug_Tot_Benes": str(100 + index),
            "Drug_Tot_Srvcs": str(300 + index),
            "Drug_Sbmtd_Chrg": str(10000 + index),
            "Drug_Mdcr_Alowd_Amt": str(8000 + index),
            "Drug_Mdcr_Pymt_Amt": str(7000 + index),
            "Drug_Mdcr_Stdzd_Amt": str(7100 + index),
        }
        medical_values = {
            "Med_Tot_HCPCS_Cds": str(30 + index),
            "Med_Tot_Benes": str(110 + index),
            "Med_Tot_Srvcs": str(400 + index),
            "Med_Sbmtd_Chrg": str(12000 + index),
            "Med_Mdcr_Alowd_Amt": str(9000 + index),
            "Med_Mdcr_Pymt_Amt": str(8500 + index),
            "Med_Mdcr_Stdzd_Amt": str(8600 + index),
        }

        if year == 2019:
            drug_indicator = "*"
            drug_values = {column: None for column in drug_values}

        if year == 2020:
            medical_indicator = "#"
            medical_values = {column: None for column in medical_values}

        total_beneficiaries = str([25, 75, 250, 1250, 500, 100][index])
        if invalid_numeric_value and year == 2024:
            total_beneficiaries = "not-a-number"

        row = {
            "Rndrng_NPI": f"100000000{index}",
            "Rndrng_Prvdr_Last_Org_Name": f"Provider {index}",
            "Rndrng_Prvdr_First_Name": f"First {index}",
            "Rndrng_Prvdr_MI": "A",
            "Rndrng_Prvdr_Crdntls": "MD",
            "Rndrng_Prvdr_Ent_Cd": "I",
            "Rndrng_Prvdr_St1": f"{index} Main Street",
            "Rndrng_Prvdr_St2": None,
            "Rndrng_Prvdr_City": "Baltimore",
            "Rndrng_Prvdr_State_Abrvtn": "MD",
            "Rndrng_Prvdr_State_FIPS": "24",
            "Rndrng_Prvdr_Zip5": "21201",
            "Rndrng_Prvdr_RUCA": "1",
            "Rndrng_Prvdr_RUCA_Desc": "Metropolitan",
            "Rndrng_Prvdr_Cntry": "US",
            "Rndrng_Prvdr_Type": "Internal Medicine",
            "Rndrng_Prvdr_Mdcr_Prtcptg_Ind": "Y",
            "Tot_HCPCS_Cds": str(50 + index),
            "Tot_Benes": total_beneficiaries,
            "Tot_Srvcs": str(1000 + index),
            "Tot_Sbmtd_Chrg": str(50000 + index),
            "Tot_Mdcr_Alowd_Amt": str(30000 + index),
            "Tot_Mdcr_Pymt_Amt": str(25000 + index),
            "Tot_Mdcr_Stdzd_Amt": str(25500 + index),
            "Drug_Sprsn_Ind": drug_indicator,
            "Med_Sprsn_Ind": medical_indicator,
            "Bene_Avg_Age": "72",
            "Bene_CC_PH_Diabetes_V2_Pct": ("75" if year in {2019, 2024} else "40"),
            "Bene_Avg_Risk_Scre": "1.25",
            "_source_id": "cms_physician_provider_summary",
            "_reporting_year": year,
            "_source_file": f"physician_{year}.csv",
            "_acquired_at_utc": "2026-07-28T00:00:00+00:00",
            **drug_values,
            **medical_values,
        }
        rows.append(row)

    dataframe = pd.DataFrame(rows)

    with duckdb.connect() as connection:
        connection.register("fixture", dataframe)
        connection.execute(
            f"""
            COPY fixture
            TO {sql_literal(str(path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )


def test_build_physician_silver_end_to_end(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    silver_path = tmp_path / "silver.parquet"
    suppression_path = tmp_path / "suppressions.parquet"
    quality_path = tmp_path / "quality_report.json"
    create_bronze_fixture(bronze_path)

    report = build_physician_silver(contract_path)

    assert silver_path.exists()
    assert suppression_path.exists()
    assert quality_path.exists()
    assert report["bronze_row_count"] == 6
    assert report["silver_row_count"] == 6
    assert report["reporting_years"] == list(range(2019, 2025))
    assert report["suppression_counts"] == {
        "counter_suppressed": 1,
        "primary_suppressed_fewer_than_11": 1,
    }
    assert report["top_coded_cell_count"] == 2
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
                provider_size_band,
                drug_suppression_status,
                medical_suppression_status,
                top_coded_metric_count,
                bene_cc_ph_diabetes_v2_pct_is_top_coded
            FROM read_parquet(?)
            ORDER BY reporting_year
            """,
            [str(silver_path)],
        ).fetchall()

        suppression_rows = connection.execute(
            """
            SELECT
                reporting_year,
                measure_group,
                source_indicator,
                suppression_status
            FROM read_parquet(?)
            ORDER BY reporting_year, measure_group
            """,
            [str(suppression_path)],
        ).fetchall()

    assert schema["provider_npi"] == "VARCHAR"
    assert schema["reporting_year"] == "INTEGER"
    assert schema["tot_benes"] == "BIGINT"
    assert schema["tot_mdcr_pymt_amt"] == "DECIMAL(38,6)"
    assert rows[0] == (
        2019,
        "small",
        "primary_suppressed_fewer_than_11",
        "not_suppressed",
        1,
        True,
    )
    assert rows[1][1] == "medium"
    assert rows[2][1] == "large"
    assert rows[3][1] == "very_large"
    assert rows[-1][-2:] == (1, True)
    assert suppression_rows == [
        (
            2019,
            "drug",
            "*",
            "primary_suppressed_fewer_than_11",
        ),
        (
            2020,
            "medical",
            "#",
            "counter_suppressed",
        ),
    ]


def test_build_rejects_unparseable_numeric_value(
    tmp_path: Path,
) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    create_bronze_fixture(
        bronze_path,
        invalid_numeric_value=True,
    )

    with pytest.raises(
        PhysicianSilverError,
        match="Unparseable numeric values",
    ):
        build_physician_silver(contract_path)
