import os
from pathlib import Path

import pyarrow.parquet as pq

from src.transformation.build_cost_intelligence import build_cost_intelligence
from src.transformation.cost_intelligence import OUTPUT_ORDER

ROOT = Path(__file__).resolve().parents[2]


def trusted_root() -> Path:
    return Path(
        os.environ.get("TRUSTED_CLAIMS_TEST_ROOT", ROOT / "data/curated/trusted_claims")
    )


def test_builder_writes_repeatable_typed_outputs(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = build_cost_intelligence(
        input_root=trusted_root(),
        output_root=first_root,
        sample_root=tmp_path / "samples",
        quality_report_path=tmp_path / "first.json",
    )
    second = build_cost_intelligence(
        input_root=trusted_root(),
        output_root=second_root,
        sample_root=tmp_path / "samples-two",
        quality_report_path=tmp_path / "second.json",
    )
    assert first["all_checks_passed"] is True
    assert first["ground_truth_accessed"] is False
    assert {name: first["tables"][name]["content_sha256"] for name in OUTPUT_ORDER} == {
        name: second["tables"][name]["content_sha256"] for name in OUTPUT_ORDER
    }
    for name in OUTPUT_ORDER:
        first_path = first_root / f"{name}.parquet"
        second_path = second_root / f"{name}.parquet"
        assert (
            pq.read_metadata(first_path).num_rows == first["tables"][name]["row_count"]
        )
        assert first_path.read_bytes() == second_path.read_bytes()
