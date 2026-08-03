from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from src.synthetic.synthetic_claims import SyntheticClaimError
from src.synthetic.synthetic_dimensions import (
    deterministic_integer,
    deterministic_unit,
    weighted_choice,
)

WORKFLOW_TABLES = ("claim_review", "audit_outcome", "recovery_transaction")


class SyntheticWorkflowError(SyntheticClaimError):
    """Raised when the clean review and audit workflow is invalid."""


def generate_workflow_rows(
    contract: dict[str, Any],
    configuration: dict[str, Any],
    claim_headers: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic clean reviews and zero-finding audits."""
    if configuration["generate_recovery_transactions"]:
        raise SyntheticWorkflowError(
            "M02 clean baseline does not permit recovery generation"
        )
    seed = int(contract["dataset"]["deterministic_seed"])
    eligible = sorted(
        (
            row
            for row in claim_headers
            if row["adjudication_date"] is not None
            and row["claim_status"] in {"paid", "adjusted", "denied"}
        ),
        key=lambda row: row["claim_id"],
    )
    reviews: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    review_number = 0
    for claim_number, claim in enumerate(eligible, start=1):
        if deterministic_unit(seed, "review_selection", claim_number) >= float(
            configuration["review_selection_share"]
        ):
            continue
        review_number += 1
        selected_date = claim["adjudication_date"] + timedelta(
            days=deterministic_integer(
                seed,
                "review_selection_lag",
                claim_number,
                int(configuration["selection_lag_days"]["minimum"]),
                int(configuration["selection_lag_days"]["maximum"]),
            )
        )
        completed_date = selected_date + timedelta(
            days=deterministic_integer(
                seed,
                "review_completion_lag",
                claim_number,
                int(configuration["completion_lag_days"]["minimum"]),
                int(configuration["completion_lag_days"]["maximum"]),
            )
        )
        reason = weighted_choice(
            configuration["selection_reasons"],
            deterministic_unit(seed, "review_reason", claim_number),
        )["value"]
        outcome = weighted_choice(
            configuration["clean_audit_outcomes"],
            deterministic_unit(seed, "audit_outcome", claim_number),
        )["value"]
        review_id = f"REV{review_number:010d}"
        reviews.append(
            {
                "review_id": review_id,
                "claim_id": claim["claim_id"],
                "review_status": "completed",
                "selected_date": selected_date,
                "completed_date": completed_date,
                "selection_reason": reason,
            }
        )
        audits.append(
            {
                "audit_id": f"AUD{review_number:010d}",
                "review_id": review_id,
                "claim_id": claim["claim_id"],
                "outcome": outcome,
                "confirmed_amount": Decimal(
                    str(configuration["confirmed_amount"])
                ).quantize(Decimal("0.01")),
                "outcome_date": completed_date,
            }
        )
    return {
        "claim_review": reviews,
        "audit_outcome": audits,
        "recovery_transaction": [],
    }


def validate_workflow_rows(
    rows: dict[str, list[dict[str, Any]]],
    claim_headers: list[dict[str, Any]],
    contract: dict[str, Any],
) -> dict[str, bool]:
    """Validate clean workflow relationships, dates, amounts, and boundaries."""
    reviews = rows["claim_review"]
    audits = rows["audit_outcome"]
    recoveries = rows["recovery_transaction"]
    claims = {row["claim_id"]: row for row in claim_headers}
    reviews_by_id = {row["review_id"]: row for row in reviews}
    audit_by_review = {row["review_id"]: row for row in audits}
    clean_outcomes = {"no_issue", "inconclusive"}
    checks = {
        "reviews_nonempty": bool(reviews),
        "review_claim_foreign_key": all(row["claim_id"] in claims for row in reviews),
        "review_dates_valid": all(
            claims[row["claim_id"]]["adjudication_date"]
            < row["selected_date"]
            <= row["completed_date"]
            for row in reviews
        ),
        "reviews_completed": all(
            row["review_status"] == "completed" for row in reviews
        ),
        "one_audit_per_review": len(audits) == len(reviews)
        and set(audit_by_review) == set(reviews_by_id),
        "audit_relationships_valid": all(
            row["review_id"] in reviews_by_id
            and row["claim_id"] == reviews_by_id[row["review_id"]]["claim_id"]
            for row in audits
        ),
        "audit_dates_valid": all(
            row["outcome_date"] == reviews_by_id[row["review_id"]]["completed_date"]
            for row in audits
        ),
        "clean_audit_outcomes_only": all(
            row["outcome"] in clean_outcomes for row in audits
        ),
        "confirmed_amounts_zero": all(row["confirmed_amount"] == 0 for row in audits),
        "recovery_table_empty": not recoveries,
        "no_m03_anomaly_labels": contract["governance"][
            "clean_baseline_contains_intentional_anomalies"
        ]
        is False,
    }
    return checks
