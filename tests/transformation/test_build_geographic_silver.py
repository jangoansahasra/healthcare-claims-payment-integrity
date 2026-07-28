from pathlib import Path

import duckdb
import pytest
import yaml

from src.transformation.build_geographic_silver import (
    build_geographic_silver,
)
from src.transformation.geographic_silver import (
    SilverTransformationError,
    sql_literal,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CONTRACT_PATH = PROJECT_ROOT / "config" / "geographic_silver.yml"


def create_fixture_contract(tmp_path: Path) -> Path:
    contract = yaml.safe_load(BASE_CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["paths"] = {
        "bronze_input": str(tmp_path / "bronze.parquet"),
        "silver_output": str(tmp_path / "silver.parquet"),
        "value_status_output": str(tmp_path / "value_status.parquet"),
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
    include_invalid_value: bool = False,
) -> None:
    rows = []

    for index, year in enumerate(range(2014, 2025)):
        geography_type = index % 3

        if geography_type == 0:
            geography_level = "National"
            geography_name = "National"
            geography_code = None
        elif geography_type == 1:
            geography_level = "State"
            geography_name = f"State {index}"
            geography_code = f"{index + 1:02d}"
        else:
            geography_level = "County"
            geography_name = f"County {index}"
            geography_code = f"{index + 1:05d}"

        age_level = ["All", "<65", ">=65"][index % 3]
        beneficiary_count = str(1000 + index)
        payment_amount = str(500000 + index * 1000)

        if index == 0:
            beneficiary_count = "*"
        elif index == 1:
            beneficiary_count = "NA"

        if index == 2:
            payment_amount = "NA"

        if include_invalid_value and year == 2024:
            beneficiary_count = "not-a-number"

        rows.append(
            (
                str(year),
                geography_level,
                geography_name,
                geography_code,
                age_level,
                beneficiary_count,
                payment_amount,
                "52.5",
                "cms_geographic_variation",
                2024,
                "fixture.csv",
                "2026-07-26T00:00:00+00:00",
            )
        )

    with duckdb.connect() as connection:
        connection.execute(
            """
            CREATE TABLE bronze (
                YEAR VARCHAR,
                BENE_GEO_LVL VARCHAR,
                BENE_GEO_DESC VARCHAR,
                BENE_GEO_CD VARCHAR,
                BENE_AGE_LVL VARCHAR,
                BENES_TOTAL_CNT VARCHAR,
                TOT_MDCR_PYMT_AMT VARCHAR,
                BENE_FEML_PCT VARCHAR,
                _source_id VARCHAR,
                _reporting_year INTEGER,
                _source_file VARCHAR,
                _acquired_at_utc VARCHAR
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO bronze
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.execute(
            f"""
            COPY bronze
            TO {sql_literal(str(path))}
            (FORMAT PARQUET, COMPRESSION ZSTD)
            """
        )


def test_build_geographic_silver_end_to_end(tmp_path: Path) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    silver_path = tmp_path / "silver.parquet"
    value_status_path = tmp_path / "value_status.parquet"
    quality_report_path = tmp_path / "quality_report.json"
    create_bronze_fixture(bronze_path)

    report = build_geographic_silver(contract_path)

    assert silver_path.exists()
    assert value_status_path.exists()
    assert quality_report_path.exists()
    assert report["bronze_row_count"] == 11
    assert report["silver_row_count"] == 11
    assert report["measure_count"] == 3
    assert report["special_value_counts"] == {
        "not_applicable": 2,
        "suppressed": 1,
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
        national_row = connection.execute(
            """
            SELECT
                geography_id,
                benes_total_cnt,
                suppressed_measure_count,
                not_applicable_measure_count
            FROM read_parquet(?)
            WHERE year = 2014
            """,
            [str(silver_path)],
        ).fetchone()
        state_id = connection.execute(
            """
            SELECT geography_id
            FROM read_parquet(?)
            WHERE year = 2015
            """,
            [str(silver_path)],
        ).fetchone()[0]
        county_id = connection.execute(
            """
            SELECT geography_id
            FROM read_parquet(?)
            WHERE year = 2016
            """,
            [str(silver_path)],
        ).fetchone()[0]
        status_rows = connection.execute(
            """
            SELECT measure_name, source_token, value_status
            FROM read_parquet(?)
            ORDER BY year, measure_name
            """,
            [str(value_status_path)],
        ).fetchall()

    assert schema["year"] == "INTEGER"
    assert schema["benes_total_cnt"] == "BIGINT"
    assert schema["tot_mdcr_pymt_amt"] == "DECIMAL(38,6)"
    assert national_row == ("US", None, 1, 0)
    assert state_id == "STATE:02"
    assert county_id == "COUNTY:00003"
    assert status_rows == [
        ("benes_total_cnt", "*", "suppressed"),
        ("benes_total_cnt", "NA", "not_applicable"),
        ("tot_mdcr_pymt_amt", "NA", "not_applicable"),
    ]


def test_build_rejects_ungoverned_numeric_value(
    tmp_path: Path,
) -> None:
    contract_path = create_fixture_contract(tmp_path)
    bronze_path = tmp_path / "bronze.parquet"
    create_bronze_fixture(
        bronze_path,
        include_invalid_value=True,
    )

    with pytest.raises(
        SilverTransformationError,
        match="Ungoverned numeric values",
    ):
        build_geographic_silver(contract_path)
