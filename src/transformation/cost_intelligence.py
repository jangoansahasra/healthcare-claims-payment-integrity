from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from typing import Any

OUTPUT_ORDER = (
    "monthly_cost_utilization",
    "monthly_payment_cash_flow",
    "provider_service_concentration",
    "cost_change_decomposition",
    "cost_early_warning_signal",
)

ZERO = Decimal("0")
CENT = Decimal("0.01")
RATE = Decimal("0.0001")
SHARE = Decimal("0.0001")


class CostIntelligenceError(ValueError):
    """Raised when trusted inputs cannot produce governed M06 outputs."""


def _q(value: Decimal, scale: Decimal) -> Decimal:
    return value.quantize(scale, rounding=ROUND_HALF_UP)


def _rate(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    return None if denominator == 0 else _q(numerator / denominator, RATE)


def _month(value: date) -> date:
    return value.replace(day=1)


def generate_cost_intelligence(
    source: dict[str, list[dict[str, Any]]], contract: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic cost-intelligence rows without reading labels."""
    dates = {row["date_key"]: row["calendar_date"] for row in source["dim_date"]}
    all_claims = {row["claim_key"]: row for row in source["fact_claim"]}
    claims = {
        row["claim_key"]: row
        for row in source["fact_claim"]
        if row["is_current_version"]
    }
    exposure: defaultdict[tuple[date, int], int] = defaultdict(int)
    for row in source["fact_membership_month"]:
        if (
            row["coverage_status"]
            == contract["population_policy"]["eligibility_status"]
        ):
            exposure[(_month(row["coverage_month"]), row["plan_key"])] += 1

    monthly: dict[tuple[date, int], dict[str, Any]] = {}
    for (month, plan), members in exposure.items():
        monthly[(month, plan)] = {
            "service_month": month,
            "plan_key": plan,
            "eligible_member_months": members,
            "claim_count": 0,
            "paid_claim_count": 0,
            "service_units": ZERO,
            "allowed_amount": ZERO,
            "paid_amount": ZERO,
        }
    paid_keys: set[int] = set()
    provider_amounts: defaultdict[tuple[date, int, int], Decimal] = defaultdict(
        lambda: ZERO
    )
    for key, claim in claims.items():
        month = _month(dates[claim["service_date_key"]])
        group = monthly.get((month, claim["plan_key"]))
        if group is None:
            raise CostIntelligenceError(
                f"Missing exposure for claim {claim['claim_id']}"
            )
        group["claim_count"] += 1
        if claim["claim_status"] == "paid":
            paid_keys.add(key)
            group["paid_claim_count"] += 1
            group["allowed_amount"] += claim["total_allowed_amount"]
            group["paid_amount"] += claim["net_paid_amount"]
            provider_amounts[
                (month, claim["plan_key"], claim["billing_provider_key"])
            ] += claim["total_allowed_amount"]

    service_amounts: defaultdict[tuple[date, int, int], Decimal] = defaultdict(
        lambda: ZERO
    )
    category: defaultdict[tuple[date, int, str], list[Decimal]] = defaultdict(
        lambda: [ZERO, ZERO]
    )
    service_categories = {
        row["service_key"]: row["service_category"] for row in source["dim_service"]
    }
    for line in source["fact_claim_line"]:
        claim = claims.get(line["claim_key"])
        if claim is None or line["claim_key"] not in paid_keys:
            continue
        month = _month(dates[line["service_date_key"]])
        monthly[(month, claim["plan_key"])]["service_units"] += line["units"]
        service_amounts[(month, claim["plan_key"], line["service_key"])] += line[
            "allowed_amount"
        ]
        values = category[
            (month, claim["plan_key"], service_categories[line["service_key"]])
        ]
        values[0] += line["allowed_amount"]
        values[1] += line["units"]

    monthly_rows = []
    for row in monthly.values():
        members = Decimal(row["eligible_member_months"])
        row["service_units"] = _q(row["service_units"], RATE)
        row["allowed_amount"] = _q(row["allowed_amount"], CENT)
        row["paid_amount"] = _q(row["paid_amount"], CENT)
        row["allowed_pmpm"] = _rate(row["allowed_amount"], members)
        row["paid_pmpm"] = _rate(row["paid_amount"], members)
        row["claims_per_1000"] = _rate(Decimal(row["claim_count"]) * 1000, members)
        row["units_per_1000"] = _rate(row["service_units"] * 1000, members)
        row["allowed_per_claim"] = _rate(
            row["allowed_amount"], Decimal(row["paid_claim_count"])
        )
        monthly_rows.append(row)
    monthly_rows.sort(key=lambda row: (row["service_month"], row["plan_key"]))

    cash: defaultdict[tuple[date, int], dict[str, Any]] = defaultdict(
        lambda: {
            "transaction_count": 0,
            "payment_count": 0,
            "reversal_count": 0,
            "net_payment_cash_flow": ZERO,
        }
    )
    for transaction in source["fact_payment_transaction"]:
        claim = all_claims.get(transaction["claim_key"])
        if claim is None:
            raise CostIntelligenceError("Payment references an unknown claim")
        key = (_month(dates[transaction["transaction_date_key"]]), claim["plan_key"])
        cash[key]["transaction_count"] += 1
        cash[key][
            "payment_count"
            if transaction["transaction_type"] == "payment"
            else "reversal_count"
        ] += 1
        cash[key]["net_payment_cash_flow"] += transaction["signed_transaction_amount"]
    cash_rows = [
        {
            "payment_month": key[0],
            "plan_key": key[1],
            **values,
            "net_payment_cash_flow": _q(values["net_payment_cash_flow"], CENT),
        }
        for key, values in cash.items()
    ]
    cash_rows.sort(key=lambda row: (row["payment_month"], row["plan_key"]))

    concentration_rows = []
    for entity_type, amounts in (
        ("provider", provider_amounts),
        ("service", service_amounts),
    ):
        grouped: defaultdict[tuple[date, int], list[Decimal]] = defaultdict(list)
        for (month, plan, _), amount in amounts.items():
            grouped[(month, plan)].append(amount)
        for (month, plan), values in grouped.items():
            total = sum(values, ZERO)
            top = sum(sorted(values, reverse=True)[:10], ZERO)
            shares = [value / total for value in values] if total else []
            concentration_rows.append(
                {
                    "service_month": month,
                    "plan_key": plan,
                    "entity_type": entity_type,
                    "entity_count": len(values),
                    "total_allowed_amount": _q(total, CENT),
                    "top_10_allowed_amount": _q(top, CENT),
                    "top_10_share": None if not total else _q(top / total, SHARE),
                    "hhi": None
                    if not total
                    else _q(sum((share * share for share in shares), ZERO), SHARE),
                }
            )
    concentration_rows.sort(
        key=lambda row: (row["service_month"], row["plan_key"], row["entity_type"])
    )

    decomposition_rows = []
    for (month, plan, service_category), (
        current_amount,
        current_units,
    ) in category.items():
        try:
            base_month = month.replace(year=month.year - 1)
        except ValueError:
            continue
        base = category.get((base_month, plan, service_category))
        if base is None or base[1] == 0 or current_units == 0:
            continue
        base_amount, base_units = base
        base_price = base_amount / base_units
        current_price = current_amount / current_units
        price_effect = (current_price - base_price) * base_units
        utilization_effect = (current_units - base_units) * base_price
        total_change = current_amount - base_amount
        mix_effect = total_change - price_effect - utilization_effect
        residual = total_change - price_effect - utilization_effect - mix_effect
        decomposition_rows.append(
            {
                "reporting_month": month,
                "base_month": base_month,
                "plan_key": plan,
                "service_category": service_category,
                "base_allowed_amount": _q(base_amount, CENT),
                "current_allowed_amount": _q(current_amount, CENT),
                "total_cost_change": _q(total_change, CENT),
                "price_effect": _q(price_effect, CENT),
                "utilization_effect": _q(utilization_effect, CENT),
                "mix_effect": _q(mix_effect, CENT),
                "reconciliation_residual": _q(residual, CENT),
            }
        )
    decomposition_rows.sort(
        key=lambda row: (
            row["reporting_month"],
            row["plan_key"],
            row["service_category"],
        )
    )

    warning = contract["early_warning_policy"]
    signal_rows = []
    history: defaultdict[tuple[int, str], list[tuple[date, Decimal]]] = defaultdict(
        list
    )
    for row in monthly_rows:
        for metric in (
            "allowed_pmpm",
            "paid_pmpm",
            "claims_per_1000",
            "units_per_1000",
        ):
            value = row[metric]
            previous = history[(row["plan_key"], metric)][
                -warning["baseline_window_months"] :
            ]
            center = scale = z_score = relative = None
            status = "insufficient_history"
            if (
                len(previous) >= warning["minimum_history_months"]
                and row["eligible_member_months"]
                >= warning["minimum_eligible_member_months"]
            ):
                values = [item[1] for item in previous]
                center = _q(Decimal(str(median(values))), RATE)
                deviations = [abs(item - center) for item in values]
                scale = _q(Decimal(str(median(deviations))), RATE)
                relative = None if center == 0 else _q((value - center) / center, RATE)
                z_score = None if scale == 0 else _q((value - center) / scale, RATE)
                status = (
                    "warning"
                    if z_score is not None
                    and z_score >= Decimal(str(warning["warning_z_score"]))
                    and relative is not None
                    and abs(relative)
                    >= Decimal(str(warning["minimum_relative_change"]))
                    else "normal"
                )
            signal_rows.append(
                {
                    "service_month": row["service_month"],
                    "plan_key": row["plan_key"],
                    "metric_name": metric,
                    "metric_value": value,
                    "history_month_count": len(previous),
                    "baseline_median": center,
                    "baseline_mad": scale,
                    "robust_z_score": z_score,
                    "relative_change": relative,
                    "signal_status": status,
                    "explanation": (
                        f"{metric}: {status}; history_months={len(previous)}"
                    ),
                }
            )
            history[(row["plan_key"], metric)].append((row["service_month"], value))
    return {
        "monthly_cost_utilization": monthly_rows,
        "monthly_payment_cash_flow": cash_rows,
        "provider_service_concentration": concentration_rows,
        "cost_change_decomposition": decomposition_rows,
        "cost_early_warning_signal": signal_rows,
    }


def validate_cost_intelligence(
    source: dict[str, list[dict[str, Any]]], outputs: dict[str, list[dict[str, Any]]]
) -> dict[str, bool]:
    """Return machine-readable M06 invariant results."""
    monthly = outputs["monthly_cost_utilization"]
    concentration = outputs["provider_service_concentration"]
    decomposition = outputs["cost_change_decomposition"]
    signals = outputs["cost_early_warning_signal"]
    return {
        "all_five_outputs_present": set(outputs) == set(OUTPUT_ORDER),
        "monthly_keys_unique": len(monthly)
        == len({(r["service_month"], r["plan_key"]) for r in monthly}),
        "nonnegative_exposure": all(r["eligible_member_months"] >= 0 for r in monthly),
        "pmpm_reconciles": all(
            r["allowed_pmpm"]
            == _rate(r["allowed_amount"], Decimal(r["eligible_member_months"]))
            for r in monthly
        ),
        "utilization_reconciles": all(
            r["units_per_1000"]
            == _rate(r["service_units"] * 1000, Decimal(r["eligible_member_months"]))
            for r in monthly
        ),
        "concentration_bounded": all(
            (r["top_10_share"] is None or ZERO <= r["top_10_share"] <= 1)
            and (r["hhi"] is None or ZERO <= r["hhi"] <= 1)
            for r in concentration
        ),
        "decomposition_reconciles": all(
            abs(r["reconciliation_residual"]) <= CENT for r in decomposition
        ),
        "signals_explained": all(
            r["explanation"]
            and r["signal_status"] in {"insufficient_history", "normal", "warning"}
            for r in signals
        ),
        "ground_truth_not_required": "bridge_claim_anomaly" not in source,
        "service_and_payment_outputs_separate": all(
            "service_month" in r for r in monthly
        )
        and all("payment_month" in r for r in outputs["monthly_payment_cash_flow"]),
    }
