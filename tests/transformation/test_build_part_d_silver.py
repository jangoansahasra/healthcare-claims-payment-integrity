from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml

from src.transformation.build_part_d_silver import build_part_d_silver
from src.transformation.geographic_silver import sql_literal
from src.transformation.part_d_silver import PartDSilverError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT_PATH = PROJECT_ROOT / "config" / "part_d_silver.yml"


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
    contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []

    for index, year in enumerate(range(2019, 2025)):
        row = {source: f"value-{index}" for source in contract["source_dimensions"]}
        row.update(
            {column: "1" for column in contract["numeric_typing"]["integer_columns"]}
        )

        for columns in contract["numeric_typing"]["decimal_measure_classes"].values():
            row.update({column: "1.5" for column in columns})

        row.update(
            {indicator: None for indicator in contract["suppression"]["indicators"]}
        )

        total_claims = [11, 56, 201, 939, 100, 500][index]
        row.update(
            {
                "Prscrbr_NPI": f"100000000{index}",
                "Prscrbr_Last_Org_Name": f"Prescriber {index}",
                "Prscrbr_First_Name": f"First {index}",
                "Prscrbr_MI": "A",
                "Prscrbr_Crdntls": "MD",
                "Prscrbr_Ent_Cd": "I",
                "Prscrbr_St1": f"{index} Main Street",
                "Prscrbr_St2": None,
                "Prscrbr_City": "Baltimore",
                "Prscrbr_State_Abrvtn": "MD",
                "Prscrbr_State_FIPS": "24",
                "Prscrbr_zip5": "21201",
                "Prscrbr_RUCA": "1",
                "Prscrbr_RUCA_Desc": "Metropolitan",
                "Prscrbr_Cntry": "US",
                "Prscrbr_Type": "Internal Medicine",
                "Prscrbr_Type_src": "Claim-Specialty",
                "Tot_Clms": str(total_claims),
                "Tot_30day_Fills": "25.5",
                "Tot_Drug_Cst": "1000.25",
                "Tot_Day_Suply": "750",
                "Tot_Benes": None if year == 2022 else "25",
                "Opioid_Prscrbr_Rate": "12.5",
                "Opioid_LA_Prscrbr_Rate": None,
                "Bene_Avg_Age": "72",
                "Bene_Avg_Risk_Scre": "1.25",
                "_source_id": "cms_part_d_provider_summary",
                "_reporting_year": year,
                "_source_file": f"part_d_{year}.csv",
                "_acquired_at_utc": "2026-07-29T00:00:00+00:00",
            }
        )

        if year == 2019:
            row["GE65_Sprsn_Flag"] = "*"
            for measure in contract["suppression"]["indicators"]["GE65_Sprsn_Flag"][
                "affected_measures"
            ]:
                row[measure] = None

        if year == 2020:
            row["Brnd_Sprsn_Flag"] = "#"
            for measure in contract["suppression"]["indicators"]["Brnd_Sprsn_Flag"][
                "affected_measures"
            ]:
                row[measure] = None

        if year == 2021:
            row["Prscrbr_Type"] = None
            row["Prscrbr_RUCA"] = ""

        if invalid_numeric_value and year == 2024:
            row["Tot_Clms"] = "not-a-number"

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


def test_build_part_d_silver_end_to_end(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    silver_path = tmp_path / "silver.parquet"
    suppression_path = tmp_path / "suppressions.parquet"
    quality_path = tmp_path / "quality_report.json"
    create_bronze_fixture(bronze_path)

    report = build_part_d_silver(contract_path)

    assert silver_path.exists()
    assert suppression_path.exists()
    assert quality_path.exists()
    assert report["bronze_row_count"] == 6
    assert report["silver_row_count"] == 6
    assert report["reporting_years"] == list(range(2019, 2025))
    assert report["measure_count"] == 56
    assert report["checks"]["require_canonical_source_schema"] is True
    assert report["suppression_counts"] == {
        "counter_suppressed": 1,
        "primary_suppressed": 1,
    }
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
                prescriber_size_band,
                prescriber_type,
                prescriber_type_is_missing,
                prescriber_ruca_code,
                prescriber_ruca_code_is_missing,
                age_65_and_older_activity_suppression_status,
                brand_suppression_status,
                tot_benes
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

    assert schema["prescriber_npi"] == "VARCHAR"
    assert schema["reporting_year"] == "INTEGER"
    assert schema["tot_clms"] == "BIGINT"
    assert schema["tot_30day_fills"] == "DECIMAL(38,6)"
    assert schema["tot_drug_cst"] == "DECIMAL(38,6)"

    assert rows[0][1] == "small"
    assert rows[0][6] == "primary_suppressed"
    assert rows[1][1] == "medium"
    assert rows[1][7] == "counter_suppressed"
    assert rows[2][1] == "large"
    assert rows[2][2:6] == (
        "Unknown",
        True,
        "Unknown",
        True,
    )
    assert rows[3][1] == "very_large"
    assert rows[3][-1] is None

    assert suppression_rows == [
        (
            2019,
            "age_65_and_older_activity",
            "*",
            "primary_suppressed",
        ),
        (
            2020,
            "brand",
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
        PartDSilverError,
        match="Unparseable numeric values",
    ):
        build_part_d_silver(contract_path)
