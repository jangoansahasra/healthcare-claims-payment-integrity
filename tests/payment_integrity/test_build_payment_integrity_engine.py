import os
from pathlib import Path

from src.payment_integrity.build_payment_integrity_engine import (
    OUTPUT_ORDER,
    build_payment_integrity_engine,
)

ROOT = Path(__file__).resolve().parents[2]
TRUSTED_ROOT = Path(
    os.environ.get(
        "TRUSTED_CLAIMS_TEST_ROOT",
        ROOT / "data/curated/trusted_claims",
    )
)


def test_full_build_meets_overall_targets_and_is_deterministic(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = build_payment_integrity_engine(
        input_root=TRUSTED_ROOT,
        output_root=first_root,
        sample_root=tmp_path / "samples-first",
        quality_report_path=tmp_path / "first.json",
    )
    second = build_payment_integrity_engine(
        input_root=TRUSTED_ROOT,
        output_root=second_root,
        sample_root=tmp_path / "samples-second",
        quality_report_path=tmp_path / "second.json",
    )

    assert first["all_checks_passed"] is True
    assert first["enabled_rule_count"] == 10
    assert first["ground_truth_label_count"] == 500
    assert first["finding_count"] == 500
    assert first["overall_evaluation"]["precision_threshold_passed"] is True
    assert first["overall_evaluation"]["recall_threshold_passed"] is True
    assert first["overall_evaluation"]["false_positive_rate_threshold_passed"] is True
    assert first["findings_frozen_sha256"] == second["findings_frozen_sha256"]
    assert first["tables"] == second["tables"]
    for name in OUTPUT_ORDER:
        assert (first_root / f"{name}.parquet").read_bytes() == (
            second_root / f"{name}.parquet"
        ).read_bytes()
