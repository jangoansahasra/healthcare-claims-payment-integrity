from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from src.synthetic.build_synthetic_dimensions import write_json_atomic
from src.synthetic.synthetic_dimensions import load_yaml

DEFAULT_CONTRACT = Path("config/fabric_deployment_contract.yml")


class FabricPackageError(ValueError):
    """Raised when a governed Fabric package cannot be built."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_bytes_atomic(value: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def _copy_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)


def _distinct_key_count(table: pa.Table, keys: list[str]) -> int:
    if not keys:
        raise FabricPackageError("Every governed table requires a primary key")
    missing = sorted(set(keys) - set(table.column_names))
    if missing:
        raise FabricPackageError("Missing primary-key columns: " + ", ".join(missing))
    rows = zip(*(table[key].to_pylist() for key in keys), strict=True)
    values = list(rows)
    if any(any(value is None for value in row) for row in values):
        raise FabricPackageError("Primary-key columns contain null values")
    return len(set(values))


def _sum_measure(table: pa.Table, column: str) -> str:
    if column not in table.column_names:
        raise FabricPackageError(f"Missing governed measure: {column}")
    total = pc.sum(table[column]).as_py()
    if total is None:
        total = Decimal("0")
    return str(total)


def _domain_sources(contract: dict[str, Any]) -> dict[str, Path]:
    sources = {
        domain: Path(details["source_root"])
        for domain, details in contract["schemas"].items()
        if domain != "evaluation_only"
    }
    evaluation = contract["schemas"]["evaluation_only"]["source_roots"]
    sources["evaluation_trusted"] = Path(evaluation["trusted"])
    sources["evaluation_payment_integrity"] = Path(evaluation["payment_integrity"])
    return sources


def _source_override(domain: str, default: Path) -> Path:
    variable = "FABRIC_" + domain.upper() + "_ROOT"
    return Path(os.environ.get(variable, default))


def _table_registry(contract: dict[str, Any]) -> list[dict[str, Any]]:
    registry = []
    domains = ("trusted", "payment_integrity", "cost_intelligence", "policy_impact")
    for domain in domains:
        access = contract["schemas"][domain]["access"]
        for table_name, mapping in contract["schemas"][domain]["tables"].items():
            registry.append(
                {
                    "domain": domain,
                    "table_name": table_name,
                    "primary_key": mapping["primary_key"],
                    "date_role": mapping["date_role"],
                    "access": access,
                    "source_domain": domain,
                }
            )
    for table_name, mapping in contract["schemas"]["evaluation_only"]["tables"].items():
        source_domain = (
            "evaluation_trusted"
            if table_name == "bridge_claim_anomaly"
            else "evaluation_payment_integrity"
        )
        registry.append(
            {
                "domain": "evaluation",
                "table_name": table_name,
                "primary_key": mapping["primary_key"],
                "date_role": "evaluation_only",
                "access": "restricted_not_for_ordinary_analytics",
                "source_domain": source_domain,
            }
        )
    return registry


def build_fabric_package(
    contract_path: Path = DEFAULT_CONTRACT,
    output_root: Path | None = None,
    quality_report_path: Path | None = None,
    sample_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Copy curated Parquet and publish a deterministic Fabric upload manifest."""
    contract = load_yaml(contract_path)
    output_root = output_root or Path(contract["deployment"]["generated_package_root"])
    quality_report_path = quality_report_path or Path(
        contract["deployment"]["quality_report"]
    )
    sample_manifest_path = sample_manifest_path or Path(
        contract["deployment"]["publishable_manifest_sample"]
    )
    sources = {
        domain: _source_override(domain, root)
        for domain, root in _domain_sources(contract).items()
    }
    measures = contract["package"]["financial_measures"]
    table_manifest = []
    for entry in _table_registry(contract):
        source = sources[entry["source_domain"]] / f"{entry['table_name']}.parquet"
        if not source.exists():
            raise FabricPackageError(f"Missing curated input: {source}")
        destination_relative = (
            Path(contract["package"]["landing_root"]) / entry["domain"] / source.name
        )
        destination = output_root / destination_relative
        _copy_atomic(source, destination)
        table = pq.read_table(source)
        key_count = _distinct_key_count(table, entry["primary_key"])
        if key_count != table.num_rows:
            raise FabricPackageError(
                f"Primary key is not unique for {entry['domain']}.{entry['table_name']}"
            )
        qualified_name = f"{entry['domain']}.{entry['table_name']}"
        governed_measures = {
            name: _sum_measure(table, name) for name in measures.get(qualified_name, [])
        }
        public_entry = {
            key: value for key, value in entry.items() if key != "source_domain"
        }
        table_manifest.append(
            {
                **public_entry,
                "landing_path": destination_relative.as_posix(),
                "row_count": table.num_rows,
                "distinct_primary_key_count": key_count,
                "parquet_sha256": _sha256(destination),
                "parquet_size_bytes": destination.stat().st_size,
                "arrow_schema": str(table.schema),
                "governed_measure_totals": governed_measures,
            }
        )
    manifest = {
        "manifest_version": contract["package"]["manifest_version"],
        "deployment_name": contract["deployment"]["name"],
        "workspace_name": contract["naming"]["workspace"],
        "lakehouse_name": contract["naming"]["lakehouse"],
        "lakehouse_schema_mode": contract["architecture"]["lakehouse_schema_mode"],
        "table_count": len(table_manifest),
        "tables": table_manifest,
    }
    manifest_path = output_root / contract["package"]["manifest_path"]
    manifest_bytes = _json_bytes(manifest)
    _write_bytes_atomic(manifest_bytes, manifest_path)
    notebook_source = Path(contract["package"]["notebook_source"])
    pipeline_source = Path(contract["package"]["pipeline_source"])
    for source, name in ((notebook_source, "notebook"), (pipeline_source, "pipeline")):
        destination = output_root / "artifacts" / source.name
        _copy_atomic(source, destination)
        manifest[name] = {
            "path": destination.relative_to(output_root).as_posix(),
            "sha256": _sha256(destination),
        }
    # Rewrite once so artifact hashes are part of the deterministic manifest.
    manifest_bytes = _json_bytes(manifest)
    _write_bytes_atomic(manifest_bytes, manifest_path)
    _write_bytes_atomic(manifest_bytes, sample_manifest_path)
    checks = {
        "all_26_tables_packaged": len(table_manifest) == 26,
        "all_row_counts_positive": all(row["row_count"] > 0 for row in table_manifest),
        "all_primary_keys_unique": all(
            row["row_count"] == row["distinct_primary_key_count"]
            for row in table_manifest
        ),
        "all_parquet_hashes_present": all(
            len(row["parquet_sha256"]) == 64 for row in table_manifest
        ),
        "evaluation_tables_restricted": all(
            row["access"] == "restricted_not_for_ordinary_analytics"
            for row in table_manifest
            if row["domain"] == "evaluation"
        ),
        "service_and_payment_roles_separate": {
            (row["table_name"], row["date_role"]) for row in table_manifest
        }
        >= {
            ("monthly_cost_utilization", "service_month"),
            ("monthly_payment_cash_flow", "payment_month"),
        },
    }
    report = {
        "report_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "execution_status": "package_ready",
        "cloud_execution_performed": False,
        "fabric_trial_activated": False,
        "table_count": len(table_manifest),
        "ordinary_table_count": sum(
            row["domain"] != "evaluation" for row in table_manifest
        ),
        "restricted_table_count": sum(
            row["domain"] == "evaluation" for row in table_manifest
        ),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "package_size_bytes": sum(
            path.stat().st_size for path in output_root.rglob("*") if path.is_file()
        ),
        "checks": checks,
        "all_checks_passed": all(checks.values()),
    }
    write_json_atomic(report, quality_report_path)
    if not report["all_checks_passed"]:
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise FabricPackageError("Fabric package checks failed: " + ", ".join(failed))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the M09 Fabric upload package.")
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--quality-report", type=Path)
    parser.add_argument("--sample-manifest", type=Path)
    args = parser.parse_args()
    report = build_fabric_package(
        args.contract, args.output_root, args.quality_report, args.sample_manifest
    )
    print(f"Fabric package tables: {report['table_count']}")
    print(f"Fabric package bytes: {report['package_size_bytes']}")
    print(f"Manifest SHA-256: {report['manifest_sha256']}")
    print(f"All package checks passed: {report['all_checks_passed']}")


if __name__ == "__main__":
    main()
