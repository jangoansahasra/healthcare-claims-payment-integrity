from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any


class TrustedClaimsError(ValueError):
    """Raised when trusted dimensional generation cannot satisfy its contract."""


TRUSTED_TABLE_ORDER = (
    "dim_member",
    "dim_provider",
    "dim_plan",
    "dim_date",
    "dim_service",
    "fact_membership_month",
    "fact_claim",
    "fact_claim_line",
    "fact_payment_transaction",
    "fact_claim_review",
    "bridge_provider_policy",
    "bridge_claim_anomaly",
)


def keyed(rows: list[dict[str, Any]], business_key: str) -> dict[str, int]:
    """Assign deterministic one-based keys over a sorted business key."""
    values = sorted({str(row[business_key]) for row in rows})
    return {value: index for index, value in enumerate(values, start=1)}


def generate_trusted_rows(
    source: dict[str, list[dict[str, Any]]],
    trusted_contract: dict[str, Any],
    operational_contract: dict[str, Any],
    anomaly_contract: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Create deterministic trusted dimensions, facts, and evaluation bridges."""
    source_variant = trusted_contract["dataset"]["default_source_variant"]
    member_keys = keyed(source["member"], "member_id")
    provider_keys = keyed(source["provider"], "provider_id")
    plan_keys = keyed(source["plan"], "plan_id")
    claim_keys = keyed(source["claim_header"], "claim_id")
    line_keys = keyed(source["claim_line"], "claim_line_id")
    payment_keys = keyed(source["payment_transaction"], "payment_transaction_id")
    review_keys = keyed(source["claim_review"], "review_id")
    policy_keys = keyed(source["policy_assignment"], "policy_assignment_id")
    injection_keys = keyed(source["anomaly_injection"], "injection_id")

    service_pairs = sorted(
        {
            (row["service_code_system"], row["service_code"])
            for row in source["claim_line"]
        }
    )
    service_keys = {pair: index for index, pair in enumerate(service_pairs, start=1)}
    procedure_categories = {
        system: mapping
        for scenario in anomaly_contract["scenarios"]
        if scenario["rule_id"] == "PI010"
        for system, mapping in scenario["injection_parameters"][
            "procedure_categories"
        ].items()
    }

    dates: set[date] = set()
    date_fields = {
        "membership_month": (
            "coverage_month",
            "coverage_start_date",
            "coverage_end_date",
        ),
        "claim_header": (
            "service_from_date",
            "service_through_date",
            "received_date",
            "adjudication_date",
        ),
        "claim_line": ("service_date",),
        "payment_transaction": ("transaction_date",),
        "claim_review": ("selected_date", "completed_date"),
        "audit_outcome": ("outcome_date",),
        "policy_assignment": ("assignment_start_date", "assignment_end_date"),
        "anomaly_injection": ("reporting_period",),
    }
    for table_name, fields in date_fields.items():
        for row in source[table_name]:
            dates.update(row[field] for field in fields if row.get(field) is not None)
    date_keys = {value: index for index, value in enumerate(sorted(dates), start=1)}
    policy_start = date.fromisoformat(
        str(operational_contract["dataset"]["policy_start_date"])
    )

    dim_member = [
        {"member_key": member_keys[row["member_id"]], **row}
        for row in sorted(source["member"], key=lambda item: item["member_id"])
    ]
    dim_provider = [
        {"provider_key": provider_keys[row["provider_id"]], **row}
        for row in sorted(source["provider"], key=lambda item: item["provider_id"])
    ]
    dim_plan = [
        {"plan_key": plan_keys[row["plan_id"]], **row}
        for row in sorted(source["plan"], key=lambda item: item["plan_id"])
    ]
    dim_date = [
        {
            "date_key": date_keys[value],
            "calendar_date": value,
            "calendar_year": value.year,
            "calendar_quarter": (value.month - 1) // 3 + 1,
            "calendar_month": value.month,
            "month_start_date": value.replace(day=1),
            "year_month": value.strftime("%Y-%m"),
            "policy_period": "post_policy" if value >= policy_start else "pre_policy",
        }
        for value in sorted(dates)
    ]
    dim_service = [
        {
            "service_key": service_keys[pair],
            "service_code_system": pair[0],
            "service_code": pair[1],
            "service_category": procedure_categories.get(pair[0], {}).get(
                pair[1], pair[0].lower().replace("-", "_")
            ),
        }
        for pair in service_pairs
    ]

    memberships = sorted(
        source["membership_month"],
        key=lambda row: (row["member_id"], row["plan_id"], row["coverage_month"]),
    )
    fact_membership = [
        {
            "membership_month_key": index,
            "member_key": member_keys[row["member_id"]],
            "plan_key": plan_keys[row["plan_id"]],
            "coverage_month_date_key": date_keys[row["coverage_month"]],
            **row,
        }
        for index, row in enumerate(memberships, start=1)
    ]

    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    payments_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source["claim_line"]:
        lines_by_claim[row["claim_id"]].append(row)
    for row in source["payment_transaction"]:
        payments_by_claim[row["claim_id"]].append(row)
    max_version: dict[str, int] = defaultdict(int)
    for row in source["claim_header"]:
        max_version[row["logical_claim_id"]] = max(
            max_version[row["logical_claim_id"]], row["claim_version_number"]
        )
    fact_claim = []
    for row in sorted(source["claim_header"], key=lambda item: item["claim_id"]):
        fact_claim.append(
            {
                "claim_key": claim_keys[row["claim_id"]],
                "prior_claim_key": claim_keys.get(row["prior_claim_id"]),
                "member_key": member_keys[row["member_id"]],
                "plan_key": plan_keys[row["plan_id"]],
                "billing_provider_key": provider_keys[row["billing_provider_id"]],
                "rendering_provider_key": provider_keys.get(
                    row["rendering_provider_id"]
                ),
                "service_date_key": date_keys[row["service_from_date"]],
                "service_through_date_key": date_keys[row["service_through_date"]],
                "received_date_key": date_keys[row["received_date"]],
                "adjudication_date_key": date_keys.get(row["adjudication_date"]),
                "claim_id": row["claim_id"],
                "logical_claim_id": row["logical_claim_id"],
                "claim_version_number": row["claim_version_number"],
                "prior_claim_id": row["prior_claim_id"],
                "claim_type": row["claim_type"],
                "claim_status": row["claim_status"],
                "principal_diagnosis_code": row["principal_diagnosis_code"],
                "is_current_version": row["claim_version_number"]
                == max_version[row["logical_claim_id"]],
                "total_charge_amount": row["total_charge_amount"],
                "total_allowed_amount": row["total_allowed_amount"],
                "total_member_liability_amount": row["total_member_liability_amount"],
                "net_paid_amount": sum(
                    (
                        item["signed_transaction_amount"]
                        for item in payments_by_claim[row["claim_id"]]
                    ),
                    start=Decimal("0.00"),
                ),
                "line_count": len(lines_by_claim[row["claim_id"]]),
                "source_variant": source_variant,
            }
        )

    fact_lines = [
        {
            "claim_line_key": line_keys[row["claim_line_id"]],
            "claim_key": claim_keys[row["claim_id"]],
            "rendering_provider_key": provider_keys.get(row["rendering_provider_id"]),
            "service_key": service_keys[
                (row["service_code_system"], row["service_code"])
            ],
            "service_date_key": date_keys[row["service_date"]],
            "claim_line_id": row["claim_line_id"],
            "claim_id": row["claim_id"],
            "line_number": row["line_number"],
            "place_of_service_code": row["place_of_service_code"],
            "units": row["units"],
            "charge_amount": row["charge_amount"],
            "allowed_amount": row["allowed_amount"],
            "member_liability_amount": row["member_liability_amount"],
            "plan_paid_amount": row["allowed_amount"] - row["member_liability_amount"],
            "source_variant": source_variant,
        }
        for row in sorted(source["claim_line"], key=lambda item: item["claim_line_id"])
    ]
    fact_payments = [
        {
            "payment_transaction_key": payment_keys[row["payment_transaction_id"]],
            "claim_key": claim_keys[row["claim_id"]],
            "transaction_date_key": date_keys[row["transaction_date"]],
            "reverses_transaction_key": payment_keys.get(
                row["reverses_transaction_id"]
            ),
            **row,
            "source_variant": source_variant,
        }
        for row in sorted(
            source["payment_transaction"],
            key=lambda item: item["payment_transaction_id"],
        )
    ]
    audit_by_review = {row["review_id"]: row for row in source["audit_outcome"]}
    fact_reviews = []
    for row in sorted(source["claim_review"], key=lambda item: item["review_id"]):
        audit = audit_by_review.get(row["review_id"])
        fact_reviews.append(
            {
                "review_key": review_keys[row["review_id"]],
                "claim_key": claim_keys[row["claim_id"]],
                "selected_date_key": date_keys.get(row["selected_date"]),
                "completed_date_key": date_keys.get(row["completed_date"]),
                "audit_outcome_date_key": date_keys.get(
                    audit["outcome_date"] if audit else None
                ),
                "review_id": row["review_id"],
                "claim_id": row["claim_id"],
                "review_status": row["review_status"],
                "selection_reason": row["selection_reason"],
                "audit_outcome": audit["outcome"] if audit else None,
                "confirmed_amount": audit["confirmed_amount"]
                if audit
                else Decimal("0.00"),
                "source_variant": source_variant,
            }
        )
    bridge_policy = [
        {
            "provider_policy_key": policy_keys[row["policy_assignment_id"]],
            "provider_key": provider_keys[row["provider_id"]],
            "assignment_start_date_key": date_keys[row["assignment_start_date"]],
            "assignment_end_date_key": date_keys.get(row["assignment_end_date"]),
            **row,
        }
        for row in sorted(
            source["policy_assignment"], key=lambda item: item["policy_assignment_id"]
        )
    ]
    bridge_anomaly = [
        {
            "anomaly_injection_key": injection_keys[row["injection_id"]],
            "claim_key": claim_keys.get(row["claim_id"]),
            "claim_line_key": line_keys.get(row["claim_line_id"]),
            "payment_transaction_key": payment_keys.get(row["payment_transaction_id"]),
            "reporting_period_date_key": date_keys.get(row["reporting_period"]),
            "injection_id": row["injection_id"],
            "rule_id": row["rule_id"],
            "label_scope": row["label_scope"],
            "target_table": row["target_table"],
            "target_record_id": row["target_record_id"],
            "provider_id": row["provider_id"],
            "expected_financial_exposure": row["expected_financial_exposure"],
            "overlap_group": row["overlap_group"],
            "evaluation_only": True,
        }
        for row in sorted(
            source["anomaly_injection"], key=lambda item: item["injection_id"]
        )
    ]
    return {
        "dim_member": dim_member,
        "dim_provider": dim_provider,
        "dim_plan": dim_plan,
        "dim_date": dim_date,
        "dim_service": dim_service,
        "fact_membership_month": fact_membership,
        "fact_claim": fact_claim,
        "fact_claim_line": fact_lines,
        "fact_payment_transaction": fact_payments,
        "fact_claim_review": fact_reviews,
        "bridge_provider_policy": bridge_policy,
        "bridge_claim_anomaly": bridge_anomaly,
    }


def validate_trusted_rows(
    source: dict[str, list[dict[str, Any]]],
    trusted: dict[str, list[dict[str, Any]]],
    trusted_contract: dict[str, Any],
) -> dict[str, bool]:
    """Return key, relationship, version, and financial quality checks."""
    claims = {row["claim_key"]: row for row in trusted["fact_claim"]}
    claim_by_id = {row["claim_id"]: row for row in trusted["fact_claim"]}
    lines_by_claim: dict[int, list[dict[str, Any]]] = defaultdict(list)
    payments_by_claim: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in trusted["fact_claim_line"]:
        lines_by_claim[row["claim_key"]].append(row)
    for row in trusted["fact_payment_transaction"]:
        payments_by_claim[row["claim_key"]].append(row)
    current_counts = Counter(
        row["logical_claim_id"] for row in claims.values() if row["is_current_version"]
    )
    anomaly_rules = {
        row["claim_key"]: row["rule_id"] for row in trusted["bridge_claim_anomaly"]
    }
    memberships = {
        (row["member_key"], row["plan_key"], row["coverage_month"])
        for row in trusted["fact_membership_month"]
    }
    dates = {row["date_key"]: row["calendar_date"] for row in trusted["dim_date"]}
    member_key_set = {row["member_key"] for row in trusted["dim_member"]}
    provider_key_set = {row["provider_key"] for row in trusted["dim_provider"]}
    plan_key_set = {row["plan_key"] for row in trusted["dim_plan"]}
    date_key_set = set(dates)
    service_key_set = {row["service_key"] for row in trusted["dim_service"]}
    line_key_set = {row["claim_line_key"] for row in trusted["fact_claim_line"]}
    payment_key_set = {
        row["payment_transaction_key"] for row in trusted["fact_payment_transaction"]
    }
    primary_keys = {
        name: table["primary_key"][0]
        for name, table in trusted_contract["tables"].items()
    }
    business_keys = {
        name: table["natural_key"] for name, table in trusted_contract["tables"].items()
    }
    checks: dict[str, bool] = {}
    for name, rows in trusted.items():
        pk = primary_keys[name]
        checks[f"{name}_primary_key"] = len(rows) == len(
            {row[pk] for row in rows}
        ) and all(row[pk] is not None for row in rows)
        natural = business_keys[name]
        checks[f"{name}_natural_key"] = len(rows) == len(
            {tuple(row[column] for column in natural) for row in rows}
        )
    checks.update(
        {
            "all_source_claims_retained": len(trusted["fact_claim"])
            == len(source["claim_header"]),
            "all_source_lines_retained": len(trusted["fact_claim_line"])
            == len(source["claim_line"]),
            "all_source_payments_retained": len(trusted["fact_payment_transaction"])
            == len(source["payment_transaction"]),
            "one_current_version": len(current_counts)
            == len({row["logical_claim_id"] for row in claims.values()})
            and all(count == 1 for count in current_counts.values()),
            "line_foreign_keys": all(
                row["claim_key"] in claims
                and (
                    row["rendering_provider_key"] is None
                    or row["rendering_provider_key"] in provider_key_set
                )
                and row["service_key"] in service_key_set
                and row["service_date_key"] in date_key_set
                for row in trusted["fact_claim_line"]
            ),
            "payment_foreign_keys": all(
                row["claim_key"] in claims
                and row["transaction_date_key"] in date_key_set
                and (
                    row["reverses_transaction_key"] is None
                    or row["reverses_transaction_key"] in payment_key_set
                )
                for row in trusted["fact_payment_transaction"]
            ),
            "membership_foreign_keys": all(
                row["member_key"] in member_key_set
                and row["plan_key"] in plan_key_set
                and row["coverage_month_date_key"] in date_key_set
                for row in trusted["fact_membership_month"]
            ),
            "claim_foreign_keys": all(
                claim["member_key"] in member_key_set
                and claim["plan_key"] in plan_key_set
                and claim["billing_provider_key"] in provider_key_set
                and (
                    claim["rendering_provider_key"] is None
                    or claim["rendering_provider_key"] in provider_key_set
                )
                and claim["service_date_key"] in date_key_set
                and claim["service_through_date_key"] in date_key_set
                and claim["received_date_key"] in date_key_set
                and (
                    claim["adjudication_date_key"] is None
                    or claim["adjudication_date_key"] in date_key_set
                )
                and (
                    claim["prior_claim_key"] is None
                    or claim["prior_claim_key"] in claims
                )
                for claim in claims.values()
            ),
            "claim_line_totals_governed": all(
                (
                    sum(
                        (line["charge_amount"] for line in lines_by_claim[key]),
                        Decimal("0.00"),
                    )
                    == claim["total_charge_amount"]
                    and sum(
                        (line["allowed_amount"] for line in lines_by_claim[key]),
                        Decimal("0.00"),
                    )
                    == claim["total_allowed_amount"]
                    and sum(
                        (
                            line["member_liability_amount"]
                            for line in lines_by_claim[key]
                        ),
                        Decimal("0.00"),
                    )
                    == claim["total_member_liability_amount"]
                )
                or anomaly_rules.get(key) == "PI005"
                for key, claim in claims.items()
            ),
            "ledger_net_paid": all(
                claim["net_paid_amount"]
                == sum(
                    (
                        payment["signed_transaction_amount"]
                        for payment in payments_by_claim[key]
                    ),
                    Decimal("0.00"),
                )
                for key, claim in claims.items()
            ),
            "denied_nonpositive_net_paid": all(
                not (claim["claim_status"] == "denied" and claim["net_paid_amount"] > 0)
                for claim in claims.values()
            ),
            "service_date_eligibility": all(
                (
                    claim["member_key"],
                    claim["plan_key"],
                    dates[claim["service_date_key"]].replace(day=1),
                )
                in memberships
                for claim in claims.values()
            ),
            "reviews_resolve": all(
                row["claim_key"] in claims
                and (
                    row["selected_date_key"] is None
                    or row["selected_date_key"] in date_key_set
                )
                and (
                    row["completed_date_key"] is None
                    or row["completed_date_key"] in date_key_set
                )
                and (
                    row["audit_outcome_date_key"] is None
                    or row["audit_outcome_date_key"] in date_key_set
                )
                for row in trusted["fact_claim_review"]
            ),
            "policy_providers_resolve": all(
                row["provider_key"] in provider_key_set
                and row["assignment_start_date_key"] in date_key_set
                and (
                    row["assignment_end_date_key"] is None
                    or row["assignment_end_date_key"] in date_key_set
                )
                for row in trusted["bridge_provider_policy"]
            ),
            "all_anomalies_retained": len(trusted["bridge_claim_anomaly"])
            == len(source["anomaly_injection"]),
            "anomaly_claims_resolve": all(
                row["claim_key"] is None or row["claim_key"] in claims
                for row in trusted["bridge_claim_anomaly"]
            ),
            "anomaly_optional_foreign_keys": all(
                (row["claim_line_key"] is None or row["claim_line_key"] in line_key_set)
                and (
                    row["payment_transaction_key"] is None
                    or row["payment_transaction_key"] in payment_key_set
                )
                and (
                    row["reporting_period_date_key"] is None
                    or row["reporting_period_date_key"] in date_key_set
                )
                for row in trusted["bridge_claim_anomaly"]
            ),
            "ground_truth_evaluation_only": all(
                row["evaluation_only"] for row in trusted["bridge_claim_anomaly"]
            )
            and all("rule_id" not in row for row in trusted["fact_claim"]),
            "claim_business_ids_resolve": all(
                claim_by_id[row["claim_id"]]["claim_key"] == row["claim_key"]
                for row in trusted["fact_claim_line"]
            ),
        }
    )
    return checks
