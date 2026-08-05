from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2

OUTPUT_ORDER = (
    "provider_month_policy_panel",
    "policy_effect_estimate",
    "event_study_estimate",
    "policy_diagnostic",
)
OUTCOMES = (
    "paid_pmpm",
    "allowed_pmpm",
    "claims_per_1000",
    "denial_rate",
    "review_rate",
)
Q = Decimal("0.0001")


class PolicyImpactError(ValueError):
    """Raised when the governed M07 design cannot be estimated."""


def _decimal(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Q, rounding=ROUND_HALF_UP)


def _event_time(month: date, policy: date) -> int:
    return (month.year - policy.year) * 12 + month.month - policy.month


def build_provider_month_panel(
    source: dict[str, list[dict[str, Any]]], contract: dict[str, Any]
) -> list[dict[str, Any]]:
    """Construct a balanced panel with pre-policy-frozen member attribution."""
    design = contract["design"]
    policy = design["policy_start_date"]
    dates = {r["date_key"]: r["calendar_date"] for r in source["dim_date"]}
    assignments = {
        r["provider_key"]: r["treatment_group"]
        for r in source["bridge_provider_policy"]
    }
    current = [r for r in source["fact_claim"] if r["is_current_version"]]
    pre_counts: dict[tuple[int, int], int] = {}
    for claim in current:
        if (
            claim["claim_status"] == "paid"
            and dates[claim["service_date_key"]] < policy
        ):
            key = (claim["member_key"], claim["billing_provider_key"])
            pre_counts[key] = pre_counts.get(key, 0) + 1
    by_member: dict[int, list[tuple[int, int]]] = {}
    for (member, provider), count in pre_counts.items():
        by_member.setdefault(member, []).append((count, provider))
    attribution = {
        member: sorted(values, key=lambda item: (-item[0], item[1]))[0][1]
        for member, values in by_member.items()
    }
    months = sorted({r["coverage_month"] for r in source["fact_membership_month"]})
    cells: dict[tuple[int, date], dict[str, Any]] = {}
    for provider, group in assignments.items():
        for month in months:
            treated = group == design["treatment_value"]
            post = month >= policy
            cells[(provider, month)] = {
                "provider_key": provider,
                "reporting_month": month,
                "treatment_group": group,
                "treatment_indicator": treated,
                "post_policy_indicator": post,
                "treatment_post": treated and post,
                "event_time": _event_time(month, policy),
                "eligible_member_months": 0,
                "claim_count": 0,
                "paid_amount": Decimal("0"),
                "allowed_amount": Decimal("0"),
                "denied_count": 0,
                "review_count": 0,
            }
    for row in source["fact_membership_month"]:
        provider = attribution.get(row["member_key"])
        if provider and row["coverage_status"] == "active":
            cells[(provider, row["coverage_month"])]["eligible_member_months"] += 1
    claim_provider: dict[int, tuple[int, date]] = {}
    for claim in current:
        month = dates[claim["service_date_key"]].replace(day=1)
        key = (claim["billing_provider_key"], month)
        cell = cells[key]
        cell["claim_count"] += 1
        claim_provider[claim["claim_key"]] = key
        if claim["claim_status"] == "paid":
            cell["paid_amount"] += claim["net_paid_amount"]
            cell["allowed_amount"] += claim["total_allowed_amount"]
        if claim["claim_status"] == "denied":
            cell["denied_count"] += 1
    for review in source["fact_claim_review"]:
        key = claim_provider.get(review["claim_key"])
        if key and review["review_status"] == "completed":
            cells[key]["review_count"] += 1
    rows = []
    for cell in cells.values():
        exposure = cell.pop("eligible_member_months")
        claims = cell["claim_count"]
        paid = cell.pop("paid_amount")
        allowed = cell.pop("allowed_amount")
        denied = cell.pop("denied_count")
        reviews = cell.pop("review_count")
        row = {**cell, "eligible_member_months": exposure}
        row["paid_pmpm"] = None if not exposure else _decimal(float(paid / exposure))
        row["allowed_pmpm"] = (
            None if not exposure else _decimal(float(allowed / exposure))
        )
        row["claims_per_1000"] = (
            None if not exposure else _decimal(claims * 1000 / exposure)
        )
        row["denial_rate"] = None if not claims else _decimal(denied / claims)
        row["review_rate"] = None if not claims else _decimal(reviews / claims)
        rows.append(row)
    rows.sort(key=lambda r: (r["provider_key"], r["reporting_month"]))
    return rows


def _fit(frame: pd.DataFrame, outcome: str, post_name: str = "treatment_post"):
    data = frame.dropna(subset=[outcome]).copy()
    formula = f"{outcome} ~ {post_name} + C(provider_key) + C(reporting_month)"
    return smf.wls(
        formula, data=data, weights=data["eligible_member_months"].clip(lower=1)
    ).fit(cov_type="cluster", cov_kwds={"groups": data["provider_key"]}), data


def estimate_policy_impact(
    panel: list[dict[str, Any]], contract: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Estimate primary, event-study, pretrend, placebo, and sensitivity results."""
    frame = pd.DataFrame(panel)
    frame["reporting_month"] = pd.to_datetime(frame["reporting_month"])
    for outcome in OUTCOMES:
        frame[outcome] = frame[outcome].map(
            lambda value: np.nan if value is None else float(value)
        )
    run_id = contract["dataset"]["deterministic_run_id"]
    effects: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for outcome in OUTCOMES:
        result, data = _fit(frame, outcome)
        for spec, coefficient in (
            ("balanced_panel", result),
            ("winsorized_99_percent", None),
            ("unweighted_provider_month", None),
        ):
            use = data.copy()
            if spec == "winsorized_99_percent":
                use[outcome] = use[outcome].clip(upper=use[outcome].quantile(0.99))
                fitted = _fit(use, outcome)[0]
            elif spec == "unweighted_provider_month":
                fitted = smf.ols(
                    f"{outcome} ~ treatment_post + C(provider_key) "
                    "+ C(reporting_month)",
                    data=use,
                ).fit(cov_type="cluster", cov_kwds={"groups": use["provider_key"]})
            else:
                fitted = coefficient
            value = float(fitted.params["treatment_post[T.True]"])
            se = float(fitted.bse["treatment_post[T.True]"])
            effects.append(
                {
                    "run_id": run_id,
                    "outcome_name": outcome,
                    "specification": spec,
                    "coefficient": _decimal(value),
                    "standard_error": _decimal(se),
                    "confidence_interval_lower": _decimal(value - 1.96 * se),
                    "confidence_interval_upper": _decimal(value + 1.96 * se),
                    "p_value": _decimal(
                        float(fitted.pvalues["treatment_post[T.True]"])
                    ),
                    "provider_count": int(use["provider_key"].nunique()),
                    "observation_count": len(use),
                }
            )

        event_data = data.copy()
        event_terms = []
        for event_time in range(-12, 6):
            if event_time == -1:
                continue
            suffix = (
                "m" + str(abs(event_time)) if event_time < 0 else "p" + str(event_time)
            )
            name = f"event_{suffix}"
            event_data[name] = (
                (event_data["event_time"] == event_time)
                & event_data["treatment_indicator"]
            ).astype(int)
            event_terms.append((event_time, name))
        formula = (
            f"{outcome} ~ {' + '.join(name for _, name in event_terms)} "
            "+ C(provider_key) + C(reporting_month)"
        )
        event_result = smf.wls(
            formula,
            data=event_data,
            weights=event_data["eligible_member_months"].clip(lower=1),
        ).fit(cov_type="cluster", cov_kwds={"groups": event_data["provider_key"]})
        for event_time, name in event_terms:
            value, se = float(event_result.params[name]), float(event_result.bse[name])
            events.append(
                {
                    "run_id": run_id,
                    "outcome_name": outcome,
                    "event_time": event_time,
                    "coefficient": _decimal(value),
                    "standard_error": _decimal(se),
                    "confidence_interval_lower": _decimal(value - 1.96 * se),
                    "confidence_interval_upper": _decimal(value + 1.96 * se),
                    "p_value": _decimal(float(event_result.pvalues[name])),
                }
            )
        pre_names = [name for time, name in event_terms if time < -1]
        beta = event_result.params[pre_names].to_numpy()
        cov = event_result.cov_params().loc[pre_names, pre_names].to_numpy()
        statistic = float(beta @ np.linalg.pinv(cov) @ beta)
        p_value = float(chi2.sf(statistic, len(pre_names)))
        diagnostics.append(
            {
                "run_id": run_id,
                "outcome_name": outcome,
                "diagnostic_name": "parallel_trends",
                "specification": "joint_wald",
                "statistic": _decimal(statistic),
                "p_value": _decimal(p_value),
                "passed": p_value >= 0.05,
                "explanation": (
                    "Joint Wald test of treatment-specific event coefficients "
                    "-12 through -2."
                ),
            }
        )
        placebo = data[data["reporting_month"] < pd.Timestamp("2026-01-01")].copy()
        placebo["placebo_post"] = placebo["treatment_indicator"] & (
            placebo["reporting_month"] >= pd.Timestamp("2025-07-01")
        )
        placebo_result, _ = _fit(placebo, outcome, "placebo_post")
        p_placebo = float(placebo_result.pvalues["placebo_post[T.True]"])
        diagnostics.append(
            {
                "run_id": run_id,
                "outcome_name": outcome,
                "diagnostic_name": "placebo_policy_date",
                "specification": "2025-07-01",
                "statistic": _decimal(
                    float(placebo_result.params["placebo_post[T.True]"])
                ),
                "p_value": _decimal(p_placebo),
                "passed": p_placebo >= 0.05,
                "explanation": "Pretreatment-only placebo interaction at July 2025.",
            }
        )
    return {
        "provider_month_policy_panel": panel,
        "policy_effect_estimate": effects,
        "event_study_estimate": events,
        "policy_diagnostic": diagnostics,
    }


def validate_policy_impact(outputs: dict[str, list[dict[str, Any]]]) -> dict[str, bool]:
    panel = outputs["provider_month_policy_panel"]
    return {
        "all_outputs_present": set(outputs) == set(OUTPUT_ORDER),
        "panel_keys_unique": len(panel)
        == len({(r["provider_key"], r["reporting_month"]) for r in panel}),
        "cohorts_nonempty": {r["treatment_group"] for r in panel}
        == {"treated", "comparison"},
        "balanced_eighteen_months": {
            sum(r["provider_key"] == p for r in panel)
            for p in {r["provider_key"] for r in panel}
        }
        == {18},
        "treatment_fixed": all(
            len({r["treatment_group"] for r in panel if r["provider_key"] == p}) == 1
            for p in {r["provider_key"] for r in panel}
        ),
        "interaction_correct": all(
            r["treatment_post"]
            == (r["treatment_indicator"] and r["post_policy_indicator"])
            for r in panel
        ),
        "reference_period_omitted": all(
            r["event_time"] != -1 for r in outputs["event_study_estimate"]
        ),
        "inference_complete": all(
            r["confidence_interval_lower"]
            <= r["coefficient"]
            <= r["confidence_interval_upper"]
            and r["standard_error"] >= 0
            for r in outputs["policy_effect_estimate"]
        ),
        "diagnostics_explained": all(
            r["explanation"] for r in outputs["policy_diagnostic"]
        ),
    }
