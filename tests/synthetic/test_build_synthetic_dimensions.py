import json
from pathlib import Path

import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import (
    GENERATED_TABLES,
    build_synthetic_dimensions,
)


def test_build_synthetic_dimensions_is_reproducible(tmp_path: Path) -> None:
    first_output = tmp_path / "first" / "full"
    first_samples = tmp_path / "first" / "samples"
    first_report = tmp_path / "first" / "quality.json"
    second_output = tmp_path / "second" / "full"
    second_samples = tmp_path / "second" / "samples"
    second_report = tmp_path / "second" / "quality.json"

    first = build_synthetic_dimensions(
        output_root=first_output,
        sample_root=first_samples,
        quality_report_path=first_report,
    )
    second = build_synthetic_dimensions(
        output_root=second_output,
        sample_root=second_samples,
        quality_report_path=second_report,
    )

    assert first["all_checks_passed"] is True
    assert second["all_checks_passed"] is True
    assert {
        name: details["content_sha256"] for name, details in first["tables"].items()
    } == {name: details["content_sha256"] for name, details in second["tables"].items()}

    for table_name in GENERATED_TABLES:
        first_path = first_output / f"{table_name}.parquet"
        second_path = second_output / f"{table_name}.parquet"
        assert (
            pq.read_metadata(first_path).num_rows
            == first["tables"][table_name]["row_count"]
        )
        assert first_path.read_bytes() == second_path.read_bytes()
        assert (first_samples / f"{table_name}_sample.csv").read_bytes() == (
            second_samples / f"{table_name}_sample.csv"
        ).read_bytes()

    persisted = json.loads(first_report.read_text(encoding="utf-8"))
    assert persisted["all_checks_passed"] is True


def test_build_writes_expected_population_counts(tmp_path: Path) -> None:
    report = build_synthetic_dimensions(
        output_root=tmp_path / "full",
        sample_root=tmp_path / "samples",
        quality_report_path=tmp_path / "quality.json",
    )

    assert report["tables"]["member"]["row_count"] == 10000
    assert report["tables"]["provider"]["row_count"] == 200
    assert report["tables"]["provider_contract"]["row_count"] == 800
    assert report["tables"]["policy_assignment"]["row_count"] == 200
    assert report["tables"]["membership_month"]["row_count"] >= 10000 * 6
