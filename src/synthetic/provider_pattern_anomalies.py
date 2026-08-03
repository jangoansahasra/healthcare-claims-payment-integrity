from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from src.synthetic.record_level_anomalies import (
    SyntheticAnomalyError,
    deterministic_rank,
    governed_value_type,
    serialized_value,
)

PROVIDER_PATTERN_RULES = ("PI007", "PI008")
PROVIDER_CHANGED_TABLES = (
    "claim_header",
    "claim_line",
    "adjudication_event",
    "payment_transaction",
)


def inject_provider_pattern_anomalies(
    stage: dict[str, list[dict[str, Any]]],
    existing_injections: list[dict[str, Any]],
    existing_changes: list[dict[str, Any]],
    anomaly_contract: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Inject reconciled PI007 amount outliers and PI008 provider-month surges."""
    seed = int(anomaly_contract["dataset"]["deterministic_seed"])
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    scenarios = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    providers = {row["provider_id"]: row for row in stage["provider"]}
    headers = [dict(row) for row in stage["claim_header"]]
    lines = [dict(row) for row in stage["claim_line"]]
    events = [dict(row) for row in stage["adjudication_event"]]
    payments = [dict(row) for row in stage["payment_transaction"]]
    header_by_id = {row["claim_id"]: row for row in headers}
    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    events_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    payments_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lines:
        lines_by_claim[row["claim_id"]].append(row)
    for row in events:
        events_by_claim[row["claim_id"]].append(row)
    for row in payments:
        payments_by_claim[row["claim_id"]].append(row)
    excluded_claims = {row["claim_id"] for row in existing_injections}
    injections = [dict(row) for row in existing_injections]
    changes = [dict(row) for row in existing_changes]
    next_injection = max(int(row["injection_id"][3:]) for row in injections) + 1
    next_logical = max(int(row["logical_claim_id"][3:]) for row in headers) + 1
    next_line = max(int(row["claim_line_id"][3:]) for row in lines) + 1
    next_event = max(int(row["adjudication_event_id"][3:]) for row in events) + 1
    next_payment = max(int(row["payment_transaction_id"][3:]) for row in payments) + 1

    def add_change(
        injection_id: str,
        operation: str,
        table: str,
        record_id: str,
        column: str,
        before: Any,
        after: Any,
        violation: bool,
    ) -> None:
        sequence = 1 + sum(row["injection_id"] == injection_id for row in changes)
        value = after if after is not None else before
        changes.append(
            {
                "injection_id": injection_id,
                "change_sequence_number": sequence,
                "field_operation": operation,
                "target_table": table,
                "target_record_id": record_id,
                "column_name": column,
                "governed_value_type": governed_value_type(value),
                "before_value": serialized_value(before),
                "after_value": serialized_value(after),
                "expected_contract_violation": violation,
            }
        )

    peer_lines: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in lines:
        header = header_by_id[line["claim_id"]]
        specialty = providers[header["billing_provider_id"]]["specialty_group"]
        peer_lines[(specialty, line["service_code_system"])].append(line)
    pi007_candidates = []
    minimum_peers = int(
        scenarios["PI007"]["injection_parameters"]["minimum_peer_count"]
    )
    for line in lines:
        header = header_by_id[line["claim_id"]]
        if (
            header["claim_status"] not in {"paid", "adjusted"}
            or line["claim_id"] in excluded_claims
            or not payments_by_claim[line["claim_id"]]
        ):
            continue
        specialty = providers[header["billing_provider_id"]]["specialty_group"]
        peers = peer_lines[(specialty, line["service_code_system"])]
        if len(peers) >= minimum_peers:
            pi007_candidates.append(line)
    ranked_lines = sorted(
        pi007_candidates,
        key=lambda row: deterministic_rank(seed, "pi007_target", row["claim_line_id"]),
    )
    selected_pi007 = []
    selected_claims: set[str] = set()
    for line in ranked_lines:
        if line["claim_id"] not in selected_claims:
            selected_pi007.append(line)
            selected_claims.add(line["claim_id"])
        if len(selected_pi007) == target_count:
            break
    if len(selected_pi007) != target_count:
        raise SyntheticAnomalyError("Insufficient disjoint PI007 targets")

    for line in selected_pi007:
        injection_id = f"INJ{next_injection:010d}"
        next_injection += 1
        header = header_by_id[line["claim_id"]]
        specialty = providers[header["billing_provider_id"]]["specialty_group"]
        peers = peer_lines[(specialty, line["service_code_system"])]
        peer_max = max(row["allowed_amount"] for row in peers)
        multiplier = Decimal(
            str(scenarios["PI007"]["injection_parameters"]["peer_threshold_multiplier"])
        )
        new_allowed = (peer_max * multiplier).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        allowed_ratio = line["allowed_amount"] / line["charge_amount"]
        new_charge = (new_allowed / allowed_ratio).quantize(Decimal("0.01"))
        liability_ratio = (
            line["member_liability_amount"] / line["allowed_amount"]
            if line["allowed_amount"]
            else Decimal("0")
        )
        new_liability = (new_allowed * liability_ratio).quantize(Decimal("0.01"))
        deltas = {
            "charge_amount": new_charge - line["charge_amount"],
            "allowed_amount": new_allowed - line["allowed_amount"],
            "member_liability_amount": new_liability - line["member_liability_amount"],
        }
        for column, new_value in (
            ("charge_amount", new_charge),
            ("allowed_amount", new_allowed),
            ("member_liability_amount", new_liability),
        ):
            before = line[column]
            line[column] = new_value
            add_change(
                injection_id,
                "update",
                "claim_line",
                line["claim_line_id"],
                column,
                before,
                new_value,
                column in {"charge_amount", "allowed_amount"},
            )
        header_columns = {
            "total_charge_amount": deltas["charge_amount"],
            "total_allowed_amount": deltas["allowed_amount"],
            "total_member_liability_amount": deltas["member_liability_amount"],
        }
        for column, delta in header_columns.items():
            before = header[column]
            header[column] += delta
            add_change(
                injection_id,
                "update",
                "claim_header",
                header["claim_id"],
                column,
                before,
                header[column],
                False,
            )
        payment = next(
            row
            for row in payments_by_claim[header["claim_id"]]
            if row["transaction_type"] == "payment"
        )
        exposure = deltas["allowed_amount"] - deltas["member_liability_amount"]
        before_payment = payment["signed_transaction_amount"]
        payment["signed_transaction_amount"] += exposure
        add_change(
            injection_id,
            "update",
            "payment_transaction",
            payment["payment_transaction_id"],
            "signed_transaction_amount",
            before_payment,
            payment["signed_transaction_amount"],
            False,
        )
        injections.append(
            {
                "injection_id": injection_id,
                "rule_id": "PI007",
                "target_table": "claim_line",
                "target_record_id": line["claim_line_id"],
                "claim_id": header["claim_id"],
                "claim_line_id": line["claim_line_id"],
                "payment_transaction_id": payment["payment_transaction_id"],
                "provider_id": header["billing_provider_id"],
                "reporting_period": header["service_from_date"].replace(day=1),
                "injection_method": scenarios["PI007"]["injection_method"],
                "label_scope": scenarios["PI007"]["label_scope"],
                "overlap_group": None,
                "expected_financial_exposure": exposure,
                "deterministic_seed": seed,
                "contract_version": anomaly_contract["contract_version"],
                "synthetic_record": True,
            }
        )

    policy_start = date(2026, 1, 1)
    provider_month_claims: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(
        list
    )
    for header in headers:
        if header["claim_id"] in excluded_claims | selected_claims:
            continue
        if not any(
            row["signed_transaction_amount"] > 0
            for row in payments_by_claim[header["claim_id"]]
        ):
            continue
        month = header["service_from_date"].replace(day=1)
        provider_month_claims[(header["billing_provider_id"], month)].append(header)
    baseline_provider_month: dict[tuple[str, date], int] = defaultdict(int)
    for header in headers:
        baseline_provider_month[
            (
                header["billing_provider_id"],
                header["service_from_date"].replace(day=1),
            )
        ] += 1
    provider_history: dict[str, dict[date, int]] = defaultdict(dict)
    for (provider_id, month), claim_count in baseline_provider_month.items():
        if month < policy_start:
            provider_history[provider_id][month] = claim_count
    minimum_months = int(
        scenarios["PI008"]["injection_parameters"]["minimum_historical_months"]
    )
    minimum_claims = int(
        scenarios["PI008"]["injection_parameters"]["minimum_historical_claims"]
    )
    period_candidates = []
    for (provider_id, month), month_headers in provider_month_claims.items():
        history = provider_history[provider_id]
        if (
            month >= policy_start
            and len(history) >= minimum_months
            and sum(history.values()) >= minimum_claims
            and month_headers
        ):
            period_candidates.append((provider_id, month))
    selected_periods = sorted(
        period_candidates,
        key=lambda item: deterministic_rank(
            seed, "pi008_target", f"{item[0]}:{item[1].isoformat()}"
        ),
    )[:target_count]
    if len(selected_periods) != target_count:
        raise SyntheticAnomalyError("Insufficient PI008 provider-period targets")

    surge_factor = float(
        scenarios["PI008"]["injection_parameters"]["utilization_surge_factor"]
    )
    for provider_id, month in selected_periods:
        injection_id = f"INJ{next_injection:010d}"
        next_injection += 1
        history_counts = list(provider_history[provider_id].values())
        historical_average = sum(history_counts) / len(history_counts)
        current_templates = provider_month_claims[(provider_id, month)]
        baseline_current_count = baseline_provider_month[(provider_id, month)]
        required_total = max(
            baseline_current_count + 1,
            math.floor(historical_average * surge_factor) + 1,
        )
        insert_count = required_total - baseline_current_count
        exposure = Decimal("0.00")
        first_new_claim_id = None
        for offset in range(insert_count):
            template = current_templates[offset % len(current_templates)]
            logical_id = f"LCL{next_logical:010d}"
            claim_id = f"CLM{next_logical:010d}V01"
            next_logical += 1
            first_new_claim_id = first_new_claim_id or claim_id
            new_header = dict(template)
            new_header.update(
                {
                    "claim_id": claim_id,
                    "logical_claim_id": logical_id,
                    "claim_version_number": 1,
                    "prior_claim_id": None,
                }
            )
            headers.append(new_header)
            header_by_id[claim_id] = new_header
            for column, value in new_header.items():
                add_change(
                    injection_id,
                    "insert",
                    "claim_header",
                    claim_id,
                    column,
                    None,
                    value,
                    column == "claim_id",
                )
            for source_line in lines_by_claim[template["claim_id"]]:
                new_line = dict(source_line)
                new_line["claim_line_id"] = f"LIN{next_line:012d}"
                next_line += 1
                new_line["claim_id"] = claim_id
                lines.append(new_line)
                for column, value in new_line.items():
                    add_change(
                        injection_id,
                        "insert",
                        "claim_line",
                        new_line["claim_line_id"],
                        column,
                        None,
                        value,
                        False,
                    )
            for source_event in events_by_claim[template["claim_id"]]:
                new_event = dict(source_event)
                new_event["adjudication_event_id"] = f"ADJ{next_event:012d}"
                next_event += 1
                new_event["claim_id"] = claim_id
                events.append(new_event)
                for column, value in new_event.items():
                    add_change(
                        injection_id,
                        "insert",
                        "adjudication_event",
                        new_event["adjudication_event_id"],
                        column,
                        None,
                        value,
                        False,
                    )
            for source_payment in payments_by_claim[template["claim_id"]]:
                if source_payment["transaction_type"] != "payment":
                    continue
                new_payment = dict(source_payment)
                new_payment["payment_transaction_id"] = f"PAY{next_payment:012d}"
                next_payment += 1
                new_payment["claim_id"] = claim_id
                new_payment["transaction_sequence_number"] = 1
                new_payment["reverses_transaction_id"] = None
                payments.append(new_payment)
                exposure += new_payment["signed_transaction_amount"]
                for column, value in new_payment.items():
                    add_change(
                        injection_id,
                        "insert",
                        "payment_transaction",
                        new_payment["payment_transaction_id"],
                        column,
                        None,
                        value,
                        False,
                    )
        target_record_id = f"{provider_id}:{month.isoformat()}"
        injections.append(
            {
                "injection_id": injection_id,
                "rule_id": "PI008",
                "target_table": "claim_header",
                "target_record_id": target_record_id,
                "claim_id": first_new_claim_id,
                "claim_line_id": None,
                "payment_transaction_id": None,
                "provider_id": provider_id,
                "reporting_period": month,
                "injection_method": scenarios["PI008"]["injection_method"],
                "label_scope": scenarios["PI008"]["label_scope"],
                "overlap_group": None,
                "expected_financial_exposure": exposure,
                "deterministic_seed": seed,
                "contract_version": anomaly_contract["contract_version"],
                "synthetic_record": True,
            }
        )

    extended = dict(stage)
    extended["claim_header"] = headers
    extended["claim_line"] = lines
    extended["adjudication_event"] = events
    extended["payment_transaction"] = payments
    return extended, injections, changes


def validate_provider_pattern_anomalies(
    before_stage: dict[str, list[dict[str, Any]]],
    extended: dict[str, list[dict[str, Any]]],
    injections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    anomaly_contract: dict[str, Any],
) -> dict[str, bool]:
    """Validate PI007 peer outliers and complete PI008 provider-month surges."""
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    scenarios = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    providers = {row["provider_id"]: row for row in before_stage["provider"]}
    before_headers = {row["claim_id"]: row for row in before_stage["claim_header"]}
    headers = {row["claim_id"]: row for row in extended["claim_header"]}
    before_lines = {row["claim_line_id"]: row for row in before_stage["claim_line"]}
    lines = {row["claim_line_id"]: row for row in extended["claim_line"]}
    line_totals: dict[str, list[Decimal]] = defaultdict(
        lambda: [Decimal("0"), Decimal("0"), Decimal("0")]
    )
    for row in extended["claim_line"]:
        totals = line_totals[row["claim_id"]]
        totals[0] += row["charge_amount"]
        totals[1] += row["allowed_amount"]
        totals[2] += row["member_liability_amount"]
    payment_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in extended["payment_transaction"]:
        payment_totals[row["claim_id"]] += row["signed_transaction_amount"]
    pi007 = [row for row in injections if row["rule_id"] == "PI007"]
    pi008 = [row for row in injections if row["rule_id"] == "PI008"]
    prior_claims = {
        row["claim_id"]
        for row in injections
        if row["rule_id"] not in PROVIDER_PATTERN_RULES
    }
    pi007_claims = {row["claim_id"] for row in pi007}
    inserted_header_changes = [
        row
        for row in changes
        if row["injection_id"] in {item["injection_id"] for item in pi008}
        and row["target_table"] == "claim_header"
        and row["column_name"] == "claim_id"
        and row["field_operation"] == "insert"
    ]
    inserted_claims = {row["target_record_id"] for row in inserted_header_changes}
    membership = {
        (row["member_id"], row["plan_id"], row["coverage_month"])
        for row in before_stage["membership_month"]
    }
    contracts = {
        (row["provider_id"], row["plan_id"])
        for row in before_stage["provider_contract"]
    }
    before_provider_month: dict[tuple[str, date], int] = defaultdict(int)
    after_provider_month: dict[tuple[str, date], int] = defaultdict(int)
    for row in before_stage["claim_header"]:
        before_provider_month[
            (row["billing_provider_id"], row["service_from_date"].replace(day=1))
        ] += 1
    for row in extended["claim_header"]:
        after_provider_month[
            (row["billing_provider_id"], row["service_from_date"].replace(day=1))
        ] += 1
    peer_allowed: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for row in before_stage["claim_line"]:
        header = before_headers[row["claim_id"]]
        specialty = providers[header["billing_provider_id"]]["specialty_group"]
        peer_allowed[(specialty, row["service_code_system"])].append(
            row["allowed_amount"]
        )
    multiplier = Decimal(
        str(scenarios["PI007"]["injection_parameters"]["peer_threshold_multiplier"])
    )
    surge_factor = float(
        scenarios["PI008"]["injection_parameters"]["utilization_surge_factor"]
    )
    prior_counts = {
        rule_id: sum(row["rule_id"] == rule_id for row in injections)
        for rule_id in ("PI001", "PI002", "PI003", "PI004", "PI005", "PI006")
    }
    all_ids = {
        "claim": [row["claim_id"] for row in extended["claim_header"]],
        "line": [row["claim_line_id"] for row in extended["claim_line"]],
        "event": [
            row["adjudication_event_id"] for row in extended["adjudication_event"]
        ],
        "payment": [
            row["payment_transaction_id"] for row in extended["payment_transaction"]
        ],
    }
    return {
        "total_injection_count": len(injections) == target_count * 8,
        "pi007_count": len(pi007) == target_count,
        "pi008_count": len(pi008) == target_count,
        "prior_counts_preserved": all(
            count == target_count for count in prior_counts.values()
        ),
        "provider_targets_avoid_prior_claims": pi007_claims.isdisjoint(prior_claims)
        and inserted_claims.isdisjoint(prior_claims),
        "pi007_pi008_disjoint": pi007_claims.isdisjoint(inserted_claims),
        "all_identifiers_unique": all(
            len(values) == len(set(values)) for values in all_ids.values()
        ),
        "pi007_above_peer_threshold": all(
            lines[item["claim_line_id"]]["allowed_amount"]
            > max(
                peer_allowed[
                    (
                        providers[headers[item["claim_id"]]["billing_provider_id"]][
                            "specialty_group"
                        ],
                        lines[item["claim_line_id"]]["service_code_system"],
                    )
                ]
            )
            * multiplier
            - Decimal("0.01")
            for item in pi007
        ),
        "pi007_reconciliation": all(
            line_totals[item["claim_id"]]
            == [
                headers[item["claim_id"]]["total_charge_amount"],
                headers[item["claim_id"]]["total_allowed_amount"],
                headers[item["claim_id"]]["total_member_liability_amount"],
            ]
            and payment_totals[item["claim_id"]]
            == headers[item["claim_id"]]["total_allowed_amount"]
            - headers[item["claim_id"]]["total_member_liability_amount"]
            for item in pi007
        ),
        "pi008_surges_exceed_factor": all(
            after_provider_month[(item["provider_id"], item["reporting_period"])]
            > (
                sum(
                    count
                    for (provider_id, month), count in before_provider_month.items()
                    if provider_id == item["provider_id"] and month < date(2026, 1, 1)
                )
                / sum(
                    1
                    for provider_id, month in before_provider_month
                    if provider_id == item["provider_id"] and month < date(2026, 1, 1)
                )
            )
            * surge_factor
            for item in pi008
        ),
        "pi008_inserted_claims_nonempty": bool(inserted_claims),
        "pi008_eligibility_valid": all(
            (
                headers[claim_id]["member_id"],
                headers[claim_id]["plan_id"],
                headers[claim_id]["service_from_date"].replace(day=1),
            )
            in membership
            for claim_id in inserted_claims
        ),
        "pi008_contracts_valid": all(
            (
                headers[claim_id]["billing_provider_id"],
                headers[claim_id]["plan_id"],
            )
            in contracts
            for claim_id in inserted_claims
        ),
        "pi008_reconciliation": all(
            line_totals[claim_id]
            == [
                headers[claim_id]["total_charge_amount"],
                headers[claim_id]["total_allowed_amount"],
                headers[claim_id]["total_member_liability_amount"],
            ]
            and payment_totals[claim_id]
            == headers[claim_id]["total_allowed_amount"]
            - headers[claim_id]["total_member_liability_amount"]
            for claim_id in inserted_claims
        ),
        "existing_lines_except_pi007_unchanged": all(
            row == lines[line_id]
            for line_id, row in before_lines.items()
            if line_id not in {item["claim_line_id"] for item in pi007}
        ),
        "unchanged_tables_preserved": all(
            extended[name] == before_stage[name]
            for name in before_stage
            if name not in PROVIDER_CHANGED_TABLES
        ),
        "all_injections_have_lineage": {row["injection_id"] for row in injections}
        == {row["injection_id"] for row in changes},
        "positive_provider_exposure": all(
            row["expected_financial_exposure"] > 0 for row in (*pi007, *pi008)
        ),
    }
