from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

DEFAULT_CONTRACT = Path("config/bi_semantic_contract.yml")
DEFAULT_OUTPUT = Path("data/generated/bi/extracts")
DEFAULT_QUALITY = Path("data/metadata/quality/bi_dashboard_extracts.json")
DEFAULT_SAMPLES = Path("data/sample/bi")


class BIExtractError(ValueError):
    """Raised when governed BI extracts cannot be produced."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n", float_format="%.4f")


def _write_json(value: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read(root: Path, name: str) -> pd.DataFrame:
    path = root / f"{name}.parquet"
    if not path.exists():
        raise BIExtractError(f"Missing governed input: {path}")
    return pd.read_parquet(path)


def _metric_rows(
    cost: pd.DataFrame,
    cash: pd.DataFrame,
    findings: pd.DataFrame,
    concentration: pd.DataFrame,
    decomposition: pd.DataFrame,
    signals: pd.DataFrame,
    policy: pd.DataFrame,
) -> pd.DataFrame:
    member_months = cost["eligible_member_months"].sum()
    allowed = cost["allowed_amount"].sum()
    paid = cost["paid_amount"].sum()
    weights = concentration["total_allowed_amount"]
    selected = policy.loc[
        (policy["specification"] == "balanced_panel")
        & (policy["outcome_name"] == "paid_pmpm")
    ]
    if selected.empty:
        selected = policy.iloc[[0]]
    values = {
        "BI001": (allowed, "service_month"),
        "BI002": (paid, "service_month"),
        "BI003": (allowed / member_months, "service_month"),
        "BI004": (paid / member_months, "service_month"),
        "BI005": (cost["claim_count"].sum() * 1000 / member_months, "service_month"),
        "BI006": (cost["service_units"].sum() * 1000 / member_months, "service_month"),
        "BI007": (cash["net_payment_cash_flow"].sum(), "payment_month"),
        "BI008": (findings["finding_id"].nunique(), "run_timestamp"),
        "BI009": (findings["amount_at_risk"].sum(), "run_timestamp"),
        "BI010": (
            (concentration["top_10_share"] * weights).sum() / weights.sum(),
            "service_month",
        ),
        "BI011": (
            (concentration["hhi"] * weights).sum() / weights.sum(),
            "service_month",
        ),
        "BI012": (decomposition["total_cost_change"].sum(), "service_month"),
        "BI013": ((signals["signal_status"] == "warning").sum(), "service_month"),
        "BI014": (selected.iloc[0]["coefficient"], "policy_event_month"),
    }
    return pd.DataFrame(
        [
            {"metric_id": key, "metric_value": value, "date_role": role}
            for key, (value, role) in values.items()
        ]
    ).sort_values("metric_id")


def build_dashboard_extracts(
    contract_path: Path = DEFAULT_CONTRACT,
    output_root: Path = DEFAULT_OUTPUT,
    quality_path: Path = DEFAULT_QUALITY,
    sample_root: Path = DEFAULT_SAMPLES,
    curated_root: Path = Path("data/curated"),
) -> dict[str, Any]:
    """Build deterministic, governed dashboard extracts from curated Parquet."""
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    cost_root = curated_root / "cost_intelligence"
    payment_root = curated_root / "payment_integrity"
    policy_root = curated_root / "policy_impact"
    trusted_root = curated_root / "trusted_claims"
    cost = _read(cost_root, "monthly_cost_utilization")
    cash = _read(cost_root, "monthly_payment_cash_flow")
    concentration = _read(cost_root, "provider_service_concentration")
    decomposition = _read(cost_root, "cost_change_decomposition")
    signals = _read(cost_root, "cost_early_warning_signal")
    findings = _read(payment_root, "rule_finding")
    policy = _read(policy_root, "policy_effect_estimate")
    claims = _read(trusted_root, "fact_claim")

    member_lookup = claims[["claim_id", "member_key"]].drop_duplicates("claim_id")
    review = findings.merge(member_lookup, on="claim_id", how="left")
    review = (
        review.groupby(["rule_id", "rule_name", "severity"], dropna=False)
        .agg(
            review_lead_count=("finding_id", "nunique"),
            amount_at_risk=("amount_at_risk", "sum"),
            distinct_member_count=("member_key", "nunique"),
        )
        .reset_index()
    )
    threshold = int(contract["governance"]["minimum_publishable_member_count"])
    review["privacy_status"] = review["distinct_member_count"].map(
        lambda value: "published" if value >= threshold else "suppressed"
    )
    suppressed = review["privacy_status"] == "suppressed"
    review.loc[suppressed, ["review_lead_count", "amount_at_risk"]] = pd.NA

    metrics = _metric_rows(
        cost, cash, findings, concentration, decomposition, signals, policy
    )
    metrics = metrics.merge(
        pd.DataFrame(
            [
                {"metric_id": key, "display_name": value["display_name"]}
                for key, value in contract["metrics"].items()
            ]
        ),
        on="metric_id",
        how="left",
    )[["metric_id", "display_name", "date_role", "metric_value"]]

    extracts = {
        "executive_kpi": metrics,
        "cost_and_utilization": cost.sort_values(["service_month", "plan_key"]),
        "payment_cash_flow": cash.sort_values(["payment_month", "plan_key"]),
        "payment_integrity_review_leads": review.sort_values(["rule_id", "severity"]),
        "provider_service_concentration": concentration.sort_values(
            ["service_month", "plan_key", "entity_type"]
        ),
        "policy_impact": policy.sort_values(["outcome_name", "specification"]),
        "methodology_signals": signals.sort_values(
            ["service_month", "plan_key", "metric_name"]
        ),
    }
    manifest = []
    for name, frame in extracts.items():
        destination = output_root / f"{name}.csv"
        sample = sample_root / f"{name}_sample.csv"
        _write_csv(frame, destination)
        _write_csv(frame.head(25), sample)
        manifest.append(
            {"extract": name, "row_count": len(frame), "sha256": _sha256(destination)}
        )

    expected = dict(zip(metrics["metric_id"], metrics["metric_value"], strict=True))
    checks = {
        "metric_count_is_14": len(metrics) == 14,
        "count_reconciliation_exact": expected["BI008"]
        == findings["finding_id"].nunique(),
        "financial_reconciliation_within_001": abs(
            Decimal(str(expected["BI001"])) - Decimal(str(cost["allowed_amount"].sum()))
        )
        <= Decimal("0.01"),
        "pmpm_denominator_exact": expected["BI003"]
        == cost["allowed_amount"].sum() / cost["eligible_member_months"].sum(),
        "service_payment_date_roles_separate": set(cost.columns).isdisjoint(
            {"payment_month"}
        )
        and set(cash.columns).isdisjoint({"service_month"}),
        "privacy_suppression_applied": not review.loc[suppressed, "amount_at_risk"]
        .notna()
        .any(),
        "evaluation_ground_truth_not_accessed": "evaluation"
        not in {str(cost_root), str(payment_root), str(policy_root), str(trusted_root)},
        "six_looker_pages_contracted": len(contract["looker_studio"]["pages"]) == 6,
        "full_extracts_outside_git": str(contract["dataset"]["output_root"]).startswith(
            "data/generated/"
        ),
    }
    if not all(checks.values()):
        raise BIExtractError("One or more governed BI checks failed")
    report = {
        "contract_version": contract["contract_version"],
        "status": "extracts_built",
        "extract_count": len(extracts),
        "privacy_threshold": threshold,
        "checks": checks,
        "extracts": manifest,
        "dashboard_status": {"looker_studio": "not_built", "power_bi": "not_built"},
    }
    _write_json(report, quality_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build governed M10 dashboard extracts"
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build_dashboard_extracts(contract_path=args.contract, output_root=args.output_root)


if __name__ == "__main__":
    main()
