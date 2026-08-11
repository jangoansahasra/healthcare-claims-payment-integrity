from pathlib import Path

import pandas as pd

from src.bi.build_dashboard_extracts import build_dashboard_extracts


def test_dashboard_extracts_build_and_reconcile(tmp_path: Path) -> None:
    output = tmp_path / "one"
    report = build_dashboard_extracts(
        output_root=output,
        quality_path=tmp_path / "quality.json",
        sample_root=tmp_path / "samples",
    )
    assert report["status"] == "extracts_built"
    assert report["extract_count"] == 7
    assert all(report["checks"].values())
    metrics = pd.read_csv(output / "executive_kpi.csv")
    assert set(metrics["metric_id"]) == {f"BI{number:03d}" for number in range(1, 15)}


def test_dashboard_extracts_are_deterministic(tmp_path: Path) -> None:
    reports = []
    for name in ("one", "two"):
        reports.append(
            build_dashboard_extracts(
                output_root=tmp_path / name,
                quality_path=tmp_path / f"{name}.json",
                sample_root=tmp_path / f"{name}_samples",
            )
        )
    first = {item["extract"]: item["sha256"] for item in reports[0]["extracts"]}
    second = {item["extract"]: item["sha256"] for item in reports[1]["extracts"]}
    assert first == second


def test_sensitive_groups_are_suppressed(tmp_path: Path) -> None:
    output = tmp_path / "output"
    build_dashboard_extracts(
        output_root=output,
        quality_path=tmp_path / "quality.json",
        sample_root=tmp_path / "samples",
    )
    review = pd.read_csv(output / "payment_integrity_review_leads.csv")
    suppressed = review["distinct_member_count"] < 11
    assert review.loc[suppressed, "privacy_status"].eq("suppressed").all()
    assert review.loc[suppressed, "amount_at_risk"].isna().all()
    assert review.loc[suppressed, "review_lead_count"].isna().all()


def test_service_and_payment_dates_are_separate(tmp_path: Path) -> None:
    output = tmp_path / "output"
    build_dashboard_extracts(
        output_root=output,
        quality_path=tmp_path / "quality.json",
        sample_root=tmp_path / "samples",
    )
    service = pd.read_csv(output / "cost_and_utilization.csv")
    payment = pd.read_csv(output / "payment_cash_flow.csv")
    assert "service_month" in service and "payment_month" not in service
    assert "payment_month" in payment and "service_month" not in payment
