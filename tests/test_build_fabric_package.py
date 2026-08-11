import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from src.cloud.build_fabric_package import FabricPackageError, build_fabric_package
from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/fabric_deployment_contract.yml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_at(root: Path) -> dict:
    return build_fabric_package(
        contract_path=CONTRACT_PATH,
        output_root=root / "package",
        quality_report_path=root / "quality.json",
        sample_manifest_path=root / "manifest.json",
    )


def test_full_package_is_complete_and_reproducible(tmp_path: Path) -> None:
    first = build_at(tmp_path / "first")
    second = build_at(tmp_path / "second")
    first_manifest = tmp_path / "first/package/manifest/table_manifest.json"
    second_manifest = tmp_path / "second/package/manifest/table_manifest.json"

    assert first["all_checks_passed"] is True
    assert first["table_count"] == 26
    assert first["ordinary_table_count"] == 23
    assert first["restricted_table_count"] == 3
    assert first["cloud_execution_performed"] is False
    assert first["fabric_trial_activated"] is False
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first_manifest.read_bytes() == second_manifest.read_bytes()


def test_manifest_hashes_match_copied_parquet(tmp_path: Path) -> None:
    build_at(tmp_path)
    package_root = tmp_path / "package"
    manifest = json.loads(
        (package_root / "manifest/table_manifest.json").read_text(encoding="utf-8")
    )

    for table in manifest["tables"]:
        path = package_root / table["landing_path"]
        assert path.exists()
        assert sha256(path) == table["parquet_sha256"]
        assert pq.read_metadata(path).num_rows == table["row_count"]
        assert table["row_count"] == table["distinct_primary_key_count"]


def test_manifest_keeps_evaluation_tables_restricted(tmp_path: Path) -> None:
    build_at(tmp_path)
    manifest = json.loads(
        (tmp_path / "package/manifest/table_manifest.json").read_text(encoding="utf-8")
    )
    evaluation = [row for row in manifest["tables"] if row["domain"] == "evaluation"]

    assert {row["table_name"] for row in evaluation} == {
        "bridge_claim_anomaly",
        "finding_ground_truth_match",
        "rule_evaluation",
    }
    assert all(
        row["access"] == "restricted_not_for_ordinary_analytics" for row in evaluation
    )


def test_manifest_contains_governed_financial_references(tmp_path: Path) -> None:
    build_at(tmp_path)
    manifest = json.loads(
        (tmp_path / "package/manifest/table_manifest.json").read_text(encoding="utf-8")
    )
    by_name = {
        f"{row['domain']}.{row['table_name']}": row for row in manifest["tables"]
    }

    assert set(by_name["trusted.fact_claim"]["governed_measure_totals"]) == {
        "total_allowed_amount",
        "net_paid_amount",
    }
    assert set(
        by_name["trusted.fact_payment_transaction"]["governed_measure_totals"]
    ) == {"signed_transaction_amount"}
    assert set(
        by_name["payment_integrity.rule_finding"]["governed_measure_totals"]
    ) == {"amount_at_risk"}


def test_manifest_and_artifacts_contain_no_local_absolute_path(tmp_path: Path) -> None:
    build_at(tmp_path)
    package_root = tmp_path / "package"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in package_root.rglob("*")
        if path.is_file() and path.suffix in {".json", ".py"}
    )

    assert "/Users/" not in text
    assert "subscription_id" not in text.lower()
    assert "tenant_id" not in text.lower()
    assert "@ou.edu" not in text.lower()


def test_missing_curated_input_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("FABRIC_TRUSTED_ROOT", str(empty))

    with pytest.raises(FabricPackageError, match="Missing curated input"):
        build_at(tmp_path / "result")


def test_notebook_and_pipeline_match_contract() -> None:
    contract = load_yaml(CONTRACT_PATH)
    notebook = (ROOT / contract["package"]["notebook_source"]).read_text(
        encoding="utf-8"
    )
    pipeline = json.loads(
        (ROOT / contract["package"]["pipeline_source"]).read_text(encoding="utf-8")
    )

    assert "saveAsTable" in notebook
    assert "distinct().count()" in notebook
    assert '"trusted.fabric_reconciliation_result"' in notebook
    assert 'LANDING_ROOT = "Files"' in notebook
    assert pipeline["name"] == contract["naming"]["pipeline"]
    assert pipeline["activities"][0]["notebook"] == contract["naming"]["notebook"]
    assert pipeline["success_criteria"]["required_table_count"] == 26
