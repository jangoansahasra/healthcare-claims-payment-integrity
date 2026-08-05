import os
from pathlib import Path

from src.payment_integrity.build_payment_integrity_engine import (
    build_payment_integrity_engine,
)
from src.reconciliation.build_sas_package import build_sas_package, scan_sas_log
from src.synthetic.synthetic_dimensions import load_yaml
from src.transformation.build_cost_intelligence import build_cost_intelligence
from src.transformation.build_policy_impact import build_policy_impact

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_yaml(ROOT / "config/sas_reconciliation_contract.yml")


def trusted_root() -> Path:
    return Path(
        os.environ.get("TRUSTED_CLAIMS_TEST_ROOT", ROOT / "data/curated/trusted_claims")
    )


def test_package_is_deterministic_complete_and_not_executed(tmp_path: Path) -> None:
    trusted = trusted_root()
    payment, cost, policy = tmp_path / "payment", tmp_path / "cost", tmp_path / "policy"
    build_payment_integrity_engine(
        input_root=trusted,
        output_root=payment,
        sample_root=tmp_path / "sp",
        quality_report_path=tmp_path / "p.json",
    )
    build_cost_intelligence(
        input_root=trusted,
        output_root=cost,
        sample_root=tmp_path / "sc",
        quality_report_path=tmp_path / "c.json",
    )
    build_policy_impact(
        input_root=trusted,
        output_root=policy,
        sample_root=tmp_path / "sy",
        quality_report_path=tmp_path / "y.json",
    )
    kwargs = {
        "trusted_root": trusted,
        "payment_root": payment,
        "cost_root": cost,
        "policy_root": policy,
    }
    first = build_sas_package(
        **kwargs,
        package_root=tmp_path / "first",
        evidence_path=tmp_path / "e1.json",
        sample_path=tmp_path / "s1.csv",
    )
    second = build_sas_package(
        **kwargs,
        package_root=tmp_path / "second",
        evidence_path=tmp_path / "e2.json",
        sample_path=tmp_path / "s2.csv",
    )
    assert first["all_preparation_checks_passed"] is True
    assert first["execution_status"] == "not_executed"
    assert first["sas_runtime_used"] is False
    assert first["input_file_count"] == 6
    assert first["reference_row_count"] == 181
    assert first["metric_ids"] == [f"SAS{value:03d}" for value in range(1, 13)]
    assert first["input_manifest_sha256"] == second["input_manifest_sha256"]
    assert first["reference_sha256"] == second["reference_sha256"]


def test_programs_exist_use_configurable_paths_and_cover_metrics() -> None:
    programs = [ROOT / row["path"] for row in CONTRACT["program_order"]]
    source = "\n".join(path.read_text() for path in programs)
    assert len(programs) == 7 and all(path.exists() for path in programs)
    assert "/Users/" not in source
    assert "&ROOT." in source
    assert all(f"SAS{value:03d}" in source for value in range(1, 13))


def test_log_scanner_rejects_errors_and_review_warnings() -> None:
    assert scan_sas_log("NOTE: execution completed", CONTRACT)["passed"] is True
    assert scan_sas_log("ERROR: file not found", CONTRACT)["passed"] is False
    assert (
        scan_sas_log("WARNING: converted to numeric values", CONTRACT)["passed"]
        is False
    )
