from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

from src.synthetic.record_level_anomalies import (
    SyntheticAnomalyError,
    deterministic_rank,
    governed_value_type,
    serialized_value,
)

LEDGER_TEMPORAL_RULES = ("PI003", "PI004")


def inject_ledger_temporal_anomalies(
    anomalous: dict[str, list[dict[str, Any]]],
    existing_injections: list[dict[str, Any]],
    existing_changes: list[dict[str, Any]],
    anomaly_contract: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Append PI003 ledger sequences and inject PI004 impossible dates."""
    seed = int(anomaly_contract["dataset"]["deterministic_seed"])
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    headers = {row["claim_id"]: row for row in anomalous["claim_header"]}
    payments = [dict(row) for row in anomalous["payment_transaction"]]
    excluded_claims = {row["claim_id"] for row in existing_injections}
    candidates = [
        row
        for row in payments
        if row["transaction_type"] == "payment"
        and row["signed_transaction_amount"] > 0
        and row["claim_id"] not in excluded_claims
        and row["claim_id"] in headers
    ]
    required = target_count * len(LEDGER_TEMPORAL_RULES)
    if len(candidates) < required:
        raise SyntheticAnomalyError(
            f"Need {required} eligible ledger targets; observed {len(candidates)}"
        )
    ranked = sorted(
        candidates,
        key=lambda row: deterministic_rank(
            seed, "ledger_temporal_target", row["payment_transaction_id"]
        ),
    )
    selected = {
        rule_id: ranked[index * target_count : (index + 1) * target_count]
        for index, rule_id in enumerate(LEDGER_TEMPORAL_RULES)
    }
    scenario_by_rule = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    injections = [dict(row) for row in existing_injections]
    changes = [dict(row) for row in existing_changes]
    change_sequences = Counter(row["injection_id"] for row in changes)
    next_injection = max(int(row["injection_id"][3:]) for row in injections) + 1
    next_payment = max(int(row["payment_transaction_id"][3:]) for row in payments) + 1

    def add_change(
        injection_id: str,
        operation: str,
        record_id: str,
        column: str,
        before: Any,
        after: Any,
        expected_violation: bool,
    ) -> None:
        change_sequences[injection_id] += 1
        sequence = change_sequences[injection_id]
        type_value = after if after is not None else before
        changes.append(
            {
                "injection_id": injection_id,
                "change_sequence_number": sequence,
                "field_operation": operation,
                "target_table": "payment_transaction",
                "target_record_id": record_id,
                "column_name": column,
                "governed_value_type": governed_value_type(type_value),
                "before_value": serialized_value(before),
                "after_value": serialized_value(after),
                "expected_contract_violation": expected_violation,
            }
        )

    for rule_id in LEDGER_TEMPORAL_RULES:
        scenario = scenario_by_rule[rule_id]
        for target in selected[rule_id]:
            injection_id = f"INJ{next_injection:010d}"
            next_injection += 1
            header = headers[target["claim_id"]]
            target_record_id = target["payment_transaction_id"]
            payment_transaction_id = target_record_id
            exposure = Decimal("0.00")
            if rule_id == "PI003":
                reversal_id = f"PAY{next_payment:012d}"
                next_payment += 1
                repayment_id = f"PAY{next_payment:012d}"
                next_payment += 1
                reversal = {
                    "payment_transaction_id": reversal_id,
                    "claim_id": target["claim_id"],
                    "transaction_sequence_number": 2,
                    "transaction_date": target["transaction_date"] + timedelta(days=1),
                    "transaction_type": "reversal",
                    "signed_transaction_amount": -target["signed_transaction_amount"],
                    "reverses_transaction_id": target["payment_transaction_id"],
                }
                exposure = (
                    target["signed_transaction_amount"] * Decimal("0.40")
                ).quantize(Decimal("0.01"))
                repayment = {
                    "payment_transaction_id": repayment_id,
                    "claim_id": target["claim_id"],
                    "transaction_sequence_number": 3,
                    "transaction_date": target["transaction_date"] + timedelta(days=2),
                    "transaction_type": "payment",
                    "signed_transaction_amount": exposure,
                    "reverses_transaction_id": None,
                }
                payments.extend((reversal, repayment))
                target_record_id = repayment_id
                payment_transaction_id = repayment_id
                for inserted in (reversal, repayment):
                    for column, after in inserted.items():
                        add_change(
                            injection_id,
                            "insert",
                            inserted["payment_transaction_id"],
                            column,
                            None,
                            after,
                            inserted is repayment
                            and column
                            in {
                                "transaction_type",
                                "signed_transaction_amount",
                            },
                        )
            else:
                before_date = target["transaction_date"]
                target["transaction_date"] = header["service_from_date"] - timedelta(
                    days=1
                )
                payment_transaction_id = target["payment_transaction_id"]
                add_change(
                    injection_id,
                    "update",
                    payment_transaction_id,
                    "transaction_date",
                    before_date,
                    target["transaction_date"],
                    True,
                )
            injections.append(
                {
                    "injection_id": injection_id,
                    "rule_id": rule_id,
                    "target_table": scenario["target_table"],
                    "target_record_id": target_record_id,
                    "claim_id": target["claim_id"],
                    "claim_line_id": None,
                    "payment_transaction_id": payment_transaction_id,
                    "provider_id": header["billing_provider_id"],
                    "reporting_period": header["service_from_date"].replace(day=1),
                    "injection_method": scenario["injection_method"],
                    "label_scope": scenario["label_scope"],
                    "overlap_group": None,
                    "expected_financial_exposure": exposure,
                    "deterministic_seed": seed,
                    "contract_version": anomaly_contract["contract_version"],
                    "synthetic_record": True,
                }
            )
    extended = dict(anomalous)
    extended["payment_transaction"] = payments
    return extended, injections, changes


def validate_ledger_temporal_anomalies(
    before_stage: dict[str, list[dict[str, Any]]],
    extended: dict[str, list[dict[str, Any]]],
    injections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    target_count: int,
) -> dict[str, bool]:
    """Validate PI003/PI004 counts, ledger linkage, dates, and isolation."""
    headers = {row["claim_id"]: row for row in extended["claim_header"]}
    before_payments = {
        row["payment_transaction_id"]: row
        for row in before_stage["payment_transaction"]
    }
    payments = {
        row["payment_transaction_id"]: row for row in extended["payment_transaction"]
    }
    by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in extended["payment_transaction"]:
        by_claim[row["claim_id"]].append(row)
    pi003 = [row for row in injections if row["rule_id"] == "PI003"]
    pi004 = [row for row in injections if row["rule_id"] == "PI004"]
    new_claims = {row["claim_id"] for row in (*pi003, *pi004)}
    prior_claims = {
        row["claim_id"]
        for row in injections
        if row["rule_id"] not in LEDGER_TEMPORAL_RULES
    }
    injection_ids = [row["injection_id"] for row in injections]
    payment_ids = [
        row["payment_transaction_id"] for row in extended["payment_transaction"]
    ]
    pi003_reversals = [
        row
        for row in extended["payment_transaction"]
        if row["claim_id"] in {item["claim_id"] for item in pi003}
        and row["transaction_type"] == "reversal"
    ]
    return {
        "total_injection_count": len(injections) == 300,
        "pi003_count": len(pi003) == target_count,
        "pi004_count": len(pi004) == target_count,
        "unique_injection_ids": len(injection_ids) == len(set(injection_ids)),
        "unique_payment_ids": len(payment_ids) == len(set(payment_ids)),
        "no_prior_target_overlap": new_claims.isdisjoint(prior_claims),
        "pi003_pi004_disjoint": {row["claim_id"] for row in pi003}.isdisjoint(
            {row["claim_id"] for row in pi004}
        ),
        "payment_row_delta": len(extended["payment_transaction"])
        == len(before_stage["payment_transaction"]) + 2 * target_count,
        "pi003_reversal_count": len(pi003_reversals) == target_count,
        "pi003_reversal_references_valid": all(
            row["reverses_transaction_id"] in before_payments
            and row["signed_transaction_amount"]
            == -before_payments[row["reverses_transaction_id"]][
                "signed_transaction_amount"
            ]
            for row in pi003_reversals
        ),
        "pi003_sequences_monotonic": all(
            [
                row["transaction_sequence_number"]
                for row in sorted(
                    by_claim[item["claim_id"]],
                    key=lambda row: row["transaction_sequence_number"],
                )
            ]
            == [1, 2, 3]
            for item in pi003
        ),
        "pi003_unresolved_positive_net": all(
            sum(row["signed_transaction_amount"] for row in by_claim[item["claim_id"]])
            == item["expected_financial_exposure"]
            > 0
            for item in pi003
        ),
        "pi004_dates_impossible": all(
            payments[item["payment_transaction_id"]]["transaction_date"]
            < headers[item["claim_id"]]["service_from_date"]
            for item in pi004
        ),
        "pi004_amounts_unchanged": all(
            payments[item["payment_transaction_id"]]["signed_transaction_amount"]
            == before_payments[item["payment_transaction_id"]][
                "signed_transaction_amount"
            ]
            for item in pi004
        ),
        "pi004_zero_exposure": all(
            item["expected_financial_exposure"] == 0 for item in pi004
        ),
        "all_injections_have_lineage": {row["injection_id"] for row in injections}
        == {row["injection_id"] for row in changes},
        "nonpayment_tables_unchanged": all(
            extended[name] == before_stage[name]
            for name in before_stage
            if name != "payment_transaction"
        ),
        "nontarget_payments_unchanged": all(
            payments[transaction_id] == row
            for transaction_id, row in before_payments.items()
            if row["claim_id"] not in new_claims
        ),
    }
