from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from src.synthetic.synthetic_workflow import SyntheticWorkflowError

RECORD_LEVEL_RULES = ("PI001", "PI002", "PI005", "PI006")
CHANGED_TABLES = ("claim_header", "claim_line", "payment_transaction")


class SyntheticAnomalyError(SyntheticWorkflowError):
    """Raised when controlled anomaly injection is invalid."""


def deterministic_rank(seed: int, namespace: str, value: str) -> str:
    """Return a stable target-selection rank."""
    return hashlib.sha256(f"{seed}:{namespace}:{value}".encode()).hexdigest()


def serialized_value(value: Any) -> str | None:
    """Serialize a typed scalar for field-level ground-truth lineage."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def governed_value_type(value: Any) -> str:
    """Return the contract lineage type for a scalar value."""
    if value is None:
        return "NULL"
    if isinstance(value, date):
        return "DATE"
    if isinstance(value, Decimal):
        return "DECIMAL_18_4" if value.as_tuple().exponent == -4 else "DECIMAL_18_2"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    return "VARCHAR"


def inject_record_level_anomalies(
    baseline: dict[str, list[dict[str, Any]]],
    anomaly_contract: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Inject PI001, PI002, PI005, and PI006 with complete lineage."""
    seed = int(anomaly_contract["dataset"]["deterministic_seed"])
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    headers = [dict(row) for row in baseline["claim_header"]]
    lines = [dict(row) for row in baseline["claim_line"]]
    payments = [dict(row) for row in baseline["payment_transaction"]]
    header_by_id = {row["claim_id"]: row for row in headers}
    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lines:
        lines_by_claim[row["claim_id"]].append(row)
    payment_by_claim = {row["claim_id"]: row for row in payments}
    candidates = [
        row["claim_id"]
        for row in headers
        if row["claim_status"] in {"paid", "adjusted"}
        and row["claim_id"] in payment_by_claim
        and lines_by_claim[row["claim_id"]]
    ]
    required = target_count * len(RECORD_LEVEL_RULES)
    if len(candidates) < required:
        raise SyntheticAnomalyError(
            f"Need {required} disjoint eligible claims; observed {len(candidates)}"
        )
    ranked = sorted(
        candidates,
        key=lambda claim_id: deterministic_rank(seed, "record_level_target", claim_id),
    )
    selected = {
        rule_id: ranked[index * target_count : (index + 1) * target_count]
        for index, rule_id in enumerate(RECORD_LEVEL_RULES)
    }
    scenario_by_rule = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    injections: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    next_line_number = max(int(row["claim_line_id"][3:]) for row in lines) + 1
    injection_number = 0

    def add_change(
        injection_id: str,
        operation: str,
        table: str,
        record_id: str,
        column: str,
        before: Any,
        after: Any,
        expected_violation: bool,
    ) -> None:
        sequence = 1 + sum(row["injection_id"] == injection_id for row in changes)
        type_value = after if after is not None else before
        changes.append(
            {
                "injection_id": injection_id,
                "change_sequence_number": sequence,
                "field_operation": operation,
                "target_table": table,
                "target_record_id": record_id,
                "column_name": column,
                "governed_value_type": governed_value_type(type_value),
                "before_value": serialized_value(before),
                "after_value": serialized_value(after),
                "expected_contract_violation": expected_violation,
            }
        )

    for rule_id in RECORD_LEVEL_RULES:
        scenario = scenario_by_rule[rule_id]
        for claim_id in selected[rule_id]:
            injection_number += 1
            injection_id = f"INJ{injection_number:010d}"
            header = header_by_id[claim_id]
            payment = payment_by_claim[claim_id]
            source_line = sorted(
                lines_by_claim[claim_id], key=lambda row: row["line_number"]
            )[0]
            target_table = scenario["target_table"]
            target_record_id = claim_id
            claim_line_id = None
            payment_transaction_id = None
            exposure = Decimal("0.00")

            if rule_id in {"PI001", "PI002"}:
                inserted = dict(source_line)
                inserted["claim_line_id"] = f"LIN{next_line_number:012d}"
                next_line_number += 1
                inserted["line_number"] = (
                    max(row["line_number"] for row in lines_by_claim[claim_id]) + 1
                )
                if rule_id == "PI002":
                    inserted["units"] = (
                        inserted["units"] + Decimal("0.2500")
                    ).quantize(Decimal("0.0001"))
                lines.append(inserted)
                lines_by_claim[claim_id].append(inserted)
                claim_line_id = inserted["claim_line_id"]
                target_record_id = claim_line_id
                exposure = (
                    inserted["allowed_amount"] - inserted["member_liability_amount"]
                )
                for column, after in inserted.items():
                    add_change(
                        injection_id,
                        "insert",
                        "claim_line",
                        claim_line_id,
                        column,
                        None,
                        after,
                        column in {"service_code", "service_date", "units"},
                    )
                for column in (
                    "total_charge_amount",
                    "total_allowed_amount",
                    "total_member_liability_amount",
                ):
                    line_column = {
                        "total_charge_amount": "charge_amount",
                        "total_allowed_amount": "allowed_amount",
                        "total_member_liability_amount": "member_liability_amount",
                    }[column]
                    before = header[column]
                    header[column] = before + inserted[line_column]
                    add_change(
                        injection_id,
                        "update",
                        "claim_header",
                        claim_id,
                        column,
                        before,
                        header[column],
                        False,
                    )
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
            elif rule_id == "PI005":
                before = header["total_allowed_amount"]
                exposure = Decimal("10.00")
                header["total_allowed_amount"] += exposure
                add_change(
                    injection_id,
                    "update",
                    "claim_header",
                    claim_id,
                    "total_allowed_amount",
                    before,
                    header["total_allowed_amount"],
                    True,
                )
            elif rule_id == "PI006":
                payment_transaction_id = payment["payment_transaction_id"]
                before = payment["signed_transaction_amount"]
                governed_net = (
                    header["total_allowed_amount"]
                    - header["total_member_liability_amount"]
                )
                payment["signed_transaction_amount"] = governed_net + Decimal("10.00")
                exposure = payment["signed_transaction_amount"] - before
                add_change(
                    injection_id,
                    "update",
                    "payment_transaction",
                    payment_transaction_id,
                    "signed_transaction_amount",
                    before,
                    payment["signed_transaction_amount"],
                    True,
                )

            injections.append(
                {
                    "injection_id": injection_id,
                    "rule_id": rule_id,
                    "target_table": target_table,
                    "target_record_id": target_record_id,
                    "claim_id": claim_id,
                    "claim_line_id": claim_line_id,
                    "payment_transaction_id": payment_transaction_id,
                    "provider_id": header["billing_provider_id"],
                    "reporting_period": date(
                        header["service_from_date"].year,
                        header["service_from_date"].month,
                        1,
                    ),
                    "injection_method": scenario["injection_method"],
                    "label_scope": scenario["label_scope"],
                    "overlap_group": None,
                    "expected_financial_exposure": exposure,
                    "deterministic_seed": seed,
                    "contract_version": anomaly_contract["contract_version"],
                    "synthetic_record": True,
                }
            )

    anomalous = dict(baseline)
    anomalous["claim_header"] = headers
    anomalous["claim_line"] = lines
    anomalous["payment_transaction"] = payments
    return anomalous, injections, changes


def validate_record_level_anomalies(
    baseline: dict[str, list[dict[str, Any]]],
    anomalous: dict[str, list[dict[str, Any]]],
    injections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    target_count: int,
) -> dict[str, bool]:
    """Validate counts, isolation, reconciliation, and exposure ground truth."""
    rule_counts = {
        rule_id: sum(row["rule_id"] == rule_id for row in injections)
        for rule_id in RECORD_LEVEL_RULES
    }
    claim_sets = {
        rule_id: {row["claim_id"] for row in injections if row["rule_id"] == rule_id}
        for rule_id in RECORD_LEVEL_RULES
    }
    all_selected = [claim for values in claim_sets.values() for claim in values]
    selected_claims = set(all_selected)
    baseline_headers = {row["claim_id"]: row for row in baseline["claim_header"]}
    anomalous_headers = {row["claim_id"]: row for row in anomalous["claim_header"]}
    baseline_lines = {row["claim_line_id"]: row for row in baseline["claim_line"]}
    anomalous_lines = {row["claim_line_id"]: row for row in anomalous["claim_line"]}
    baseline_payments = {
        row["payment_transaction_id"]: row for row in baseline["payment_transaction"]
    }
    anomalous_payments = {
        row["payment_transaction_id"]: row for row in anomalous["payment_transaction"]
    }
    line_totals: dict[str, list[Decimal]] = defaultdict(
        lambda: [Decimal("0"), Decimal("0"), Decimal("0")]
    )
    for row in anomalous["claim_line"]:
        totals = line_totals[row["claim_id"]]
        totals[0] += row["charge_amount"]
        totals[1] += row["allowed_amount"]
        totals[2] += row["member_liability_amount"]
    payment_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in anomalous["payment_transaction"]:
        payment_totals[row["claim_id"]] += row["signed_transaction_amount"]
    pi005 = claim_sets["PI005"]
    pi006 = claim_sets["PI006"]
    reconciled_claims = set(anomalous_headers) - pi005
    payment_reconciled_claims = set(anomalous_headers) - pi005 - pi006
    untouched_tables = set(baseline) - set(CHANGED_TABLES)
    injection_ids = [row["injection_id"] for row in injections]
    changed_injections = {row["injection_id"] for row in changes}
    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in anomalous["claim_line"]:
        lines_by_claim[row["claim_id"]].append(row)

    def exact_signature(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            row[column]
            for column in (
                "rendering_provider_id",
                "service_code_system",
                "service_code",
                "service_date",
                "place_of_service_code",
                "units",
                "charge_amount",
                "allowed_amount",
                "member_liability_amount",
            )
        )

    pi001_rows = [row for row in injections if row["rule_id"] == "PI001"]
    pi002_rows = [row for row in injections if row["rule_id"] == "PI002"]
    return {
        "rule_counts": all(count == target_count for count in rule_counts.values()),
        "unique_injection_ids": len(injection_ids) == len(set(injection_ids)),
        "disjoint_claim_targets": len(all_selected) == len(set(all_selected)),
        "all_injections_have_lineage": set(injection_ids) == changed_injections,
        "untouched_tables_equal_baseline": all(
            anomalous[name] == baseline[name] for name in untouched_tables
        ),
        "nontarget_headers_equal_baseline": all(
            anomalous_headers[claim_id] == row
            for claim_id, row in baseline_headers.items()
            if claim_id not in selected_claims
        ),
        "existing_lines_equal_baseline": all(
            anomalous_lines[line_id] == row for line_id, row in baseline_lines.items()
        ),
        "nontarget_payments_equal_baseline": all(
            anomalous_payments[transaction_id] == row
            for transaction_id, row in baseline_payments.items()
            if row["claim_id"] not in selected_claims
        ),
        "duplicate_line_delta": len(anomalous["claim_line"])
        == len(baseline["claim_line"]) + 2 * target_count,
        "pi001_exact_duplicates": all(
            sum(
                exact_signature(line)
                == exact_signature(anomalous_lines[row["claim_line_id"]])
                for line in lines_by_claim[row["claim_id"]]
            )
            >= 2
            for row in pi001_rows
        ),
        "pi002_near_duplicates": all(
            any(
                line["claim_line_id"] != row["claim_line_id"]
                and line["service_code"]
                == anomalous_lines[row["claim_line_id"]]["service_code"]
                and line["service_date"]
                == anomalous_lines[row["claim_line_id"]]["service_date"]
                and line["charge_amount"]
                == anomalous_lines[row["claim_line_id"]]["charge_amount"]
                and line["units"] != anomalous_lines[row["claim_line_id"]]["units"]
                for line in lines_by_claim[row["claim_id"]]
            )
            for row in pi002_rows
        ),
        "header_line_reconciliation_isolated": all(
            line_totals[claim_id]
            == [
                row["total_charge_amount"],
                row["total_allowed_amount"],
                row["total_member_liability_amount"],
            ]
            for claim_id, row in anomalous_headers.items()
            if claim_id in reconciled_claims
        ),
        "pi005_mismatch_count": sum(
            line_totals[claim_id][1]
            != anomalous_headers[claim_id]["total_allowed_amount"]
            for claim_id in anomalous_headers
        )
        == target_count,
        "payment_reconciliation_isolated": all(
            payment_totals[claim_id]
            == row["total_allowed_amount"] - row["total_member_liability_amount"]
            for claim_id, row in anomalous_headers.items()
            if claim_id in payment_reconciled_claims and row["claim_status"] != "denied"
        ),
        "pi006_excess_count": sum(
            payment_totals[claim_id]
            > anomalous_headers[claim_id]["total_allowed_amount"]
            - anomalous_headers[claim_id]["total_member_liability_amount"]
            for claim_id in anomalous_headers
        )
        == target_count,
        "positive_exposure": all(
            row["expected_financial_exposure"] > 0 for row in injections
        ),
        "synthetic_targets_only": all(row["synthetic_record"] for row in injections),
    }
