import os
from pathlib import Path

from src.transformation.build_policy_impact import build_policy_impact
from src.transformation.policy_impact import OUTPUT_ORDER

ROOT = Path(__file__).resolve().parents[2]


def trusted_root() -> Path:
    return Path(
        os.environ.get("TRUSTED_CLAIMS_TEST_ROOT", ROOT / "data/curated/trusted_claims")
    )


def test_builder_writes_repeatable_policy_outputs(tmp_path: Path) -> None:
    first = build_policy_impact(
        input_root=trusted_root(),
        output_root=tmp_path / "first",
        sample_root=tmp_path / "samples",
        quality_report_path=tmp_path / "first.json",
    )
    second = build_policy_impact(
        input_root=trusted_root(),
        output_root=tmp_path / "second",
        sample_root=tmp_path / "samples-two",
        quality_report_path=tmp_path / "second.json",
    )
    assert first["all_checks_passed"] is True
    assert first["ground_truth_accessed"] is False
    assert {name: first["tables"][name]["content_sha256"] for name in OUTPUT_ORDER} == {
        name: second["tables"][name]["content_sha256"] for name in OUTPUT_ORDER
    }
    for name in OUTPUT_ORDER:
        assert (tmp_path / "first" / f"{name}.parquet").read_bytes() == (
            tmp_path / "second" / f"{name}.parquet"
        ).read_bytes()
