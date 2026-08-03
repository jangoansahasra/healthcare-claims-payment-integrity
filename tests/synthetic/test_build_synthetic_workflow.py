import json
from copy import deepcopy
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from src.synthetic.build_synthetic_claims import build_synthetic_claims
from src.synthetic.build_synthetic_dimensions import build_synthetic_dimensions
from src.synthetic.build_synthetic_workflow import build_synthetic_workflow
from src.synthetic.synthetic_dimensions import load_yaml
from src.synthetic.synthetic_workflow import WORKFLOW_TABLES

ROOT = Path(__file__).resolve().parents[2]


def test_workflow_build_validates_all_fourteen_tables(tmp_path: Path) -> None:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 60
    contract["generation"]["providers"] = 40
    contract["generation"]["claim_headers"] = 300
    contract_path = tmp_path / "contract.yml"
    contract_path.write_text(
        yaml.safe_dump(contract, sort_keys=False), encoding="utf-8"
    )
    data_root = tmp_path / "generated"
    build_synthetic_dimensions(
        contract_path=contract_path,
        output_root=data_root,
        sample_root=tmp_path / "dimension_samples",
        quality_report_path=tmp_path / "dimension_quality.json",
    )
    build_synthetic_claims(
        contract_path=contract_path,
        dimension_root=data_root,
        output_root=data_root,
        sample_root=tmp_path / "claim_samples",
        quality_report_path=tmp_path / "claim_quality.json",
    )
    report = build_synthetic_workflow(
        contract_path=contract_path,
        data_root=data_root,
        sample_root=tmp_path / "workflow_samples",
        quality_report_path=tmp_path / "operational_quality.json",
    )
    first_hashes = {
        name: details["content_sha256"] for name, details in report["tables"].items()
    }
    first_workflow_bytes = {
        name: (data_root / f"{name}.parquet").read_bytes() for name in WORKFLOW_TABLES
    }
    repeated = build_synthetic_workflow(
        contract_path=contract_path,
        data_root=data_root,
        sample_root=tmp_path / "workflow_samples",
        quality_report_path=tmp_path / "operational_quality.json",
    )

    assert report["all_checks_passed"] is True
    assert {
        name: details["content_sha256"] for name, details in repeated["tables"].items()
    } == first_hashes
    assert {
        name: (data_root / f"{name}.parquet").read_bytes() for name in WORKFLOW_TABLES
    } == first_workflow_bytes
    assert len(report["tables"]) == 14
    for table_name in WORKFLOW_TABLES:
        path = data_root / f"{table_name}.parquet"
        assert path.is_file()
        assert pq.read_schema(path).names == list(
            contract["tables"][table_name]["columns"]
        )
    assert pq.read_metadata(data_root / "recovery_transaction.parquet").num_rows == 0
    assert json.loads((tmp_path / "operational_quality.json").read_text())[
        "all_checks_passed"
    ]
