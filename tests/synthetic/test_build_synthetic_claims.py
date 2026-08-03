import json
from copy import deepcopy
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from src.synthetic.build_synthetic_claims import build_synthetic_claims
from src.synthetic.build_synthetic_dimensions import build_synthetic_dimensions
from src.synthetic.synthetic_claims import CLAIM_TABLES
from src.synthetic.synthetic_dimensions import load_yaml

ROOT = Path(__file__).resolve().parents[2]


def write_small_contract(path: Path) -> None:
    contract = deepcopy(load_yaml(ROOT / "config/synthetic_data_contract.yml"))
    contract["generation"]["members"] = 60
    contract["generation"]["providers"] = 40
    contract["generation"]["claim_headers"] = 300
    path.write_text(yaml.safe_dump(contract, sort_keys=False), encoding="utf-8")


def test_claim_build_writes_contract_parquet_and_report(tmp_path: Path) -> None:
    contract_path = tmp_path / "contract.yml"
    write_small_contract(contract_path)
    dimension_root = tmp_path / "dimensions"
    build_synthetic_dimensions(
        contract_path=contract_path,
        output_root=dimension_root,
        sample_root=tmp_path / "dimension_samples",
        quality_report_path=tmp_path / "dimension_quality.json",
    )
    report = build_synthetic_claims(
        contract_path=contract_path,
        dimension_root=dimension_root,
        output_root=tmp_path / "claims",
        sample_root=tmp_path / "claim_samples",
        quality_report_path=tmp_path / "claim_quality.json",
    )

    assert report["all_checks_passed"] is True
    assert report["tables"]["claim_header"]["row_count"] == 300
    for table_name in CLAIM_TABLES:
        assert pq.read_metadata(tmp_path / "claims" / f"{table_name}.parquet").num_rows
        assert (tmp_path / "claim_samples" / f"{table_name}_sample.csv").is_file()
    assert json.loads((tmp_path / "claim_quality.json").read_text())[
        "all_checks_passed"
    ]
