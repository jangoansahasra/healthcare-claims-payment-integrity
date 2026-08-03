from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.synthetic.synthetic_dimensions import (
    SyntheticDimensionError,
    deterministic_integer,
    deterministic_unit,
    weighted_choice,
)

MONEY = Decimal("0.01")
UNITS = Decimal("0.0001")
CLAIM_TABLES = (
    "claim_header",
    "claim_line",
    "adjudication_event",
    "payment_transaction",
    "denial_outcome",
)


class SyntheticClaimError(SyntheticDimensionError):
    """Raised when clean synthetic claims cannot be generated or validated."""


def decimal_between(
    seed: int,
    namespace: str,
    index: int,
    minimum: float,
    maximum: float,
    quantum: Decimal,
) -> Decimal:
    """Return a deterministic fixed-scale decimal in the inclusive range."""
    value = Decimal(str(minimum)) + Decimal(
        str(deterministic_unit(seed, namespace, index))
    ) * (Decimal(str(maximum)) - Decimal(str(minimum)))
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def _eligible_claim_members(
    membership_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        membership_rows,
        key=lambda row: (row["coverage_month"], row["member_id"], row["plan_id"]),
    )


def generate_claim_rows(
    contract: dict[str, Any],
    configuration: dict[str, Any],
    dimensions: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Generate deterministic clean claims and append-only lifecycle records."""
    seed = int(contract["dataset"]["deterministic_seed"])
    claim_count = int(contract["generation"]["claim_headers"])
    memberships = _eligible_claim_members(dimensions["membership_month"])
    if not memberships:
        raise SyntheticClaimError("At least one membership month is required")
    membership_by_key = {
        (row["member_id"], row["plan_id"], row["coverage_month"]): row
        for row in memberships
    }

    providers_by_specialty: dict[str, list[str]] = defaultdict(list)
    for provider in dimensions["provider"]:
        providers_by_specialty[provider["specialty_group"]].append(
            provider["provider_id"]
        )
    contracted = {
        (row["provider_id"], row["plan_id"]) for row in dimensions["provider_contract"]
    }

    headers: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    denials: list[dict[str, Any]] = []
    line_sequence = event_sequence = payment_sequence = denial_sequence = 0
    previous_claim_id: str | None = None
    previous_logical_id: str | None = None
    previous_version = 0

    type_entries = configuration["claim_type_distribution"]
    for number in range(1, claim_count + 1):
        is_second_version = (
            number > 1
            and previous_claim_id is not None
            and previous_version == 1
            and deterministic_unit(seed, "claim_second_version", number)
            < float(configuration["second_version_share"])
        )
        if is_second_version:
            logical_claim_id = previous_logical_id
            version = 2
            prior_claim_id = previous_claim_id
        else:
            logical_claim_id = f"LCL{number:010d}"
            version = 1
            prior_claim_id = None
        claim_id = f"CLM{int(logical_claim_id[3:]):010d}V{version:02d}"

        if is_second_version:
            prior_header = headers[-1]
            service_from = prior_header["service_from_date"]
            service_through = prior_header["service_through_date"]
            coverage_month = date(service_from.year, service_from.month, 1)
            membership = membership_by_key[
                (prior_header["member_id"], prior_header["plan_id"], coverage_month)
            ]
            claim_type = next(
                entry
                for entry in type_entries
                if entry["value"] == prior_header["claim_type"]
            )
            provider_id = prior_header["billing_provider_id"]
            received_date = prior_header["adjudication_date"] + timedelta(days=1)
        else:
            membership = memberships[
                deterministic_integer(
                    seed, "claim_membership", number, 0, len(memberships) - 1
                )
            ]
            claim_type = weighted_choice(
                type_entries, deterministic_unit(seed, "claim_type", number)
            )
            provider_pool = sorted(
                provider_id
                for specialty in claim_type["provider_specialties"]
                for provider_id in providers_by_specialty[specialty]
                if (provider_id, membership["plan_id"]) in contracted
            )
            if not provider_pool:
                raise SyntheticClaimError(
                    f"No contracted provider for {claim_type['value']}"
                )
            provider_id = provider_pool[
                deterministic_integer(
                    seed, "claim_provider", number, 0, len(provider_pool) - 1
                )
            ]
            covered_days = (
                membership["coverage_end_date"] - membership["coverage_start_date"]
            ).days
            service_from = membership["coverage_start_date"] + timedelta(
                days=deterministic_integer(
                    seed, "claim_service_day", number, 0, covered_days
                )
            )
            stay_days = (
                deterministic_integer(
                    seed,
                    "inpatient_stay",
                    number,
                    int(configuration["inpatient_stay_days"]["minimum"]),
                    int(configuration["inpatient_stay_days"]["maximum"]),
                )
                if claim_type["value"] == "inpatient"
                else 0
            )
            service_through = min(
                service_from + timedelta(days=stay_days),
                membership["coverage_end_date"],
            )
            received_date = service_through + timedelta(
                days=deterministic_integer(
                    seed,
                    "receipt_lag",
                    number,
                    int(configuration["receipt_lag_days"]["minimum"]),
                    int(configuration["receipt_lag_days"]["maximum"]),
                )
            )
        adjudication_date = received_date + timedelta(
            days=deterministic_integer(
                seed,
                "adjudication_lag",
                number,
                int(configuration["adjudication_lag_days"]["minimum"]),
                int(configuration["adjudication_lag_days"]["maximum"]),
            )
        )
        denied = deterministic_unit(seed, "ordinary_denial", number) < float(
            configuration["ordinary_denial_share"]
        )
        line_count = deterministic_integer(
            seed,
            "claim_line_count",
            number,
            int(claim_type["line_count"]["minimum"]),
            int(claim_type["line_count"]["maximum"]),
        )
        claim_lines = []
        for line_number in range(1, line_count + 1):
            line_sequence += 1
            line_index = number * 10 + line_number
            units = Decimal(
                deterministic_integer(
                    seed,
                    "line_units",
                    line_index,
                    1,
                    int(claim_type["unit_limit"]),
                )
            )
            if claim_type.get("fractional_units") and line_number == 1:
                units += Decimal("0.5")
            units = units.quantize(UNITS)
            charge = decimal_between(
                seed,
                "line_charge",
                line_index,
                claim_type["charge_range"]["minimum"],
                claim_type["charge_range"]["maximum"],
                MONEY,
            )
            if denied:
                allowed = liability = Decimal("0.00")
            else:
                allowed_ratio = decimal_between(
                    seed,
                    "line_allowed_ratio",
                    line_index,
                    claim_type["allowed_ratio"]["minimum"],
                    claim_type["allowed_ratio"]["maximum"],
                    Decimal("0.0001"),
                )
                allowed = (charge * allowed_ratio).quantize(MONEY)
                liability_ratio = decimal_between(
                    seed,
                    "line_liability_ratio",
                    line_index,
                    configuration["member_liability_ratio"]["minimum"],
                    configuration["member_liability_ratio"]["maximum"],
                    Decimal("0.0001"),
                )
                liability = (allowed * liability_ratio).quantize(MONEY)
            service_codes = claim_type["service_codes"]
            service_code = str(
                service_codes[
                    deterministic_integer(
                        seed, "service_code", line_index, 0, len(service_codes) - 1
                    )
                ]
            )
            place_codes = claim_type["place_of_service_codes"]
            claim_lines.append(
                {
                    "claim_line_id": f"LIN{line_sequence:012d}",
                    "claim_id": claim_id,
                    "line_number": line_number,
                    "rendering_provider_id": provider_id,
                    "service_code_system": claim_type["service_code_system"],
                    "service_code": service_code,
                    "service_date": service_from,
                    "place_of_service_code": str(place_codes[0]).zfill(2),
                    "units": units,
                    "charge_amount": charge,
                    "allowed_amount": allowed,
                    "member_liability_amount": liability,
                }
            )
        lines.extend(claim_lines)
        total_charge = sum(
            (row["charge_amount"] for row in claim_lines), Decimal("0.00")
        )
        total_allowed = sum(
            (row["allowed_amount"] for row in claim_lines), Decimal("0.00")
        )
        total_liability = sum(
            (row["member_liability_amount"] for row in claim_lines),
            Decimal("0.00"),
        )
        final_status = "denied" if denied else ("adjusted" if version == 2 else "paid")
        headers.append(
            {
                "claim_id": claim_id,
                "logical_claim_id": logical_claim_id,
                "claim_version_number": version,
                "prior_claim_id": prior_claim_id,
                "member_id": membership["member_id"],
                "plan_id": membership["plan_id"],
                "billing_provider_id": provider_id,
                "rendering_provider_id": provider_id,
                "claim_type": claim_type["value"],
                "claim_status": final_status,
                "service_from_date": service_from,
                "service_through_date": service_through,
                "received_date": received_date,
                "adjudication_date": adjudication_date,
                "principal_diagnosis_code": configuration["diagnosis_codes"][
                    deterministic_integer(
                        seed,
                        "diagnosis",
                        number,
                        0,
                        len(configuration["diagnosis_codes"]) - 1,
                    )
                ],
                "total_charge_amount": total_charge,
                "total_allowed_amount": total_allowed,
                "total_member_liability_amount": total_liability,
            }
        )
        event_sequence += 1
        events.append(
            {
                "adjudication_event_id": f"ADJ{event_sequence:012d}",
                "claim_id": claim_id,
                "event_sequence_number": 1,
                "event_timestamp": datetime.combine(received_date, time(9)),
                "prior_status": None,
                "resulting_status": "received",
                "reason_code": None,
            }
        )
        event_sequence += 1
        reason = (
            configuration["denial_reason_codes"][
                deterministic_integer(
                    seed,
                    "denial_reason",
                    number,
                    0,
                    len(configuration["denial_reason_codes"]) - 1,
                )
            ]
            if denied
            else None
        )
        events.append(
            {
                "adjudication_event_id": f"ADJ{event_sequence:012d}",
                "claim_id": claim_id,
                "event_sequence_number": 2,
                "event_timestamp": datetime.combine(adjudication_date, time(15)),
                "prior_status": "received",
                "resulting_status": final_status,
                "reason_code": reason,
            }
        )
        if denied:
            denial_sequence += 1
            denials.append(
                {
                    "denial_id": f"DEN{denial_sequence:010d}",
                    "claim_id": claim_id,
                    "denial_date": adjudication_date,
                    "denial_reason_code": reason,
                    "denied_amount": total_charge,
                }
            )
        else:
            payment_sequence += 1
            payment_date = adjudication_date + timedelta(
                days=deterministic_integer(
                    seed,
                    "payment_lag",
                    number,
                    int(configuration["payment_lag_days"]["minimum"]),
                    int(configuration["payment_lag_days"]["maximum"]),
                )
            )
            payments.append(
                {
                    "payment_transaction_id": f"PAY{payment_sequence:012d}",
                    "claim_id": claim_id,
                    "transaction_sequence_number": 1,
                    "transaction_date": payment_date,
                    "transaction_type": "payment",
                    "signed_transaction_amount": total_allowed - total_liability,
                    "reverses_transaction_id": None,
                }
            )
        previous_claim_id = claim_id
        previous_logical_id = logical_claim_id
        previous_version = version

    return dict(
        zip(CLAIM_TABLES, (headers, lines, events, payments, denials), strict=True)
    )


def validate_claim_rows(
    rows: dict[str, list[dict[str, Any]]],
    contract: dict[str, Any],
    dimensions: dict[str, list[dict[str, Any]]],
) -> dict[str, bool]:
    """Validate lifecycle keys, relationships, dates, and financial equations."""
    headers = rows["claim_header"]
    lines = rows["claim_line"]
    events = rows["adjudication_event"]
    payments = rows["payment_transaction"]
    denials = rows["denial_outcome"]
    header_ids = {row["claim_id"] for row in headers}
    header_by_id = {row["claim_id"]: row for row in headers}
    line_totals: dict[str, list[Decimal]] = defaultdict(
        lambda: [Decimal("0"), Decimal("0"), Decimal("0")]
    )
    for row in lines:
        totals = line_totals[row["claim_id"]]
        totals[0] += row["charge_amount"]
        totals[1] += row["allowed_amount"]
        totals[2] += row["member_liability_amount"]
    payment_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in payments:
        payment_totals[row["claim_id"]] += row["signed_transaction_amount"]
    coverage = {
        (row["member_id"], row["plan_id"], row["coverage_month"])
        for row in dimensions["membership_month"]
    }
    contracts = {
        (row["provider_id"], row["plan_id"]) for row in dimensions["provider_contract"]
    }
    denied_ids = {row["claim_id"] for row in denials}
    checks = {
        "claim_header_row_count": len(headers)
        == int(contract["generation"]["claim_headers"]),
        "all_claim_types_present": {row["claim_type"] for row in headers}
        == set(contract["allowed_values"]["claim_type"]),
        "claim_header_primary_key": len(header_ids) == len(headers),
        "claim_line_foreign_key": all(row["claim_id"] in header_ids for row in lines),
        "event_foreign_key": all(row["claim_id"] in header_ids for row in events),
        "payment_foreign_key": all(row["claim_id"] in header_ids for row in payments),
        "denial_foreign_key": all(row["claim_id"] in header_ids for row in denials),
        "eligibility_at_service": all(
            (
                row["member_id"],
                row["plan_id"],
                date(row["service_from_date"].year, row["service_from_date"].month, 1),
            )
            in coverage
            for row in headers
        ),
        "provider_contract_at_service": all(
            (row["billing_provider_id"], row["plan_id"]) in contracts for row in headers
        ),
        "lifecycle_dates": all(
            row["service_from_date"]
            <= row["service_through_date"]
            <= row["received_date"]
            <= row["adjudication_date"]
            for row in headers
        ),
        "line_header_reconciliation": all(
            line_totals[row["claim_id"]]
            == [
                row["total_charge_amount"],
                row["total_allowed_amount"],
                row["total_member_liability_amount"],
            ]
            for row in headers
        ),
        "nonnegative_amounts": all(
            row[column] >= 0
            for row in lines
            for column in (
                "charge_amount",
                "allowed_amount",
                "member_liability_amount",
            )
        ),
        "allowed_not_above_charge": all(
            row["allowed_amount"] <= row["charge_amount"] for row in lines
        ),
        "liability_not_above_allowed": all(
            row["member_liability_amount"] <= row["allowed_amount"] for row in lines
        ),
        "payment_reconciliation": all(
            payment_totals[row["claim_id"]]
            == row["total_allowed_amount"] - row["total_member_liability_amount"]
            for row in headers
        ),
        "denied_claims_have_no_payment": all(
            payment_totals[claim_id] == 0 for claim_id in denied_ids
        ),
        "denials_match_status": denied_ids
        == {row["claim_id"] for row in headers if row["claim_status"] == "denied"},
        "version_links_valid": all(
            (row["claim_version_number"] == 1 and row["prior_claim_id"] is None)
            or (
                row["claim_version_number"] == 2 and row["prior_claim_id"] in header_ids
            )
            for row in headers
        ),
        "version_identity_stable": all(
            row["claim_version_number"] == 1
            or all(
                row[column] == header_by_id[row["prior_claim_id"]][column]
                for column in (
                    "logical_claim_id",
                    "member_id",
                    "plan_id",
                    "billing_provider_id",
                    "claim_type",
                    "service_from_date",
                    "service_through_date",
                )
            )
            for row in headers
        ),
        "version_dates_monotonic": all(
            row["claim_version_number"] == 1
            or row["received_date"]
            > header_by_id[row["prior_claim_id"]]["adjudication_date"]
            for row in headers
        ),
        "adjudication_event_count": len(events) == 2 * len(headers),
        "fractional_units_preserved": any(row["units"] % 1 for row in lines),
        "no_intentional_anomalies": contract["governance"][
            "clean_baseline_contains_intentional_anomalies"
        ]
        is False,
    }
    return checks
