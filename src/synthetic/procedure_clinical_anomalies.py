from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any

from src.synthetic.record_level_anomalies import (
    SyntheticAnomalyError,
    deterministic_rank,
    governed_value_type,
    serialized_value,
)

PROCEDURE_CLINICAL_RULES = ("PI009", "PI010")
PROCEDURE_CLINICAL_CHANGED_TABLES = (
    "claim_header",
    "claim_line",
    "payment_transaction",
)


def inject_procedure_clinical_anomalies(
    stage: dict[str, list[dict[str, Any]]],
    existing_injections: list[dict[str, Any]],
    existing_changes: list[dict[str, Any]],
    anomaly_contract: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Append deterministic PI009 frequency and PI010 compatibility anomalies."""
    seed = int(anomaly_contract["dataset"]["deterministic_seed"])
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    scenarios = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    headers = [dict(row) for row in stage["claim_header"]]
    lines = [dict(row) for row in stage["claim_line"]]
    payments = [dict(row) for row in stage["payment_transaction"]]
    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    payments_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lines:
        lines_by_claim[row["claim_id"]].append(row)
    for row in payments:
        payments_by_claim[row["claim_id"]].append(row)
    excluded_claims = {row["claim_id"] for row in existing_injections}
    injections = [dict(row) for row in existing_injections]
    changes = [dict(row) for row in existing_changes]
    next_injection = max(int(row["injection_id"][3:]) for row in injections) + 1
    next_line = max(int(row["claim_line_id"][3:]) for row in lines) + 1

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

    limits = scenarios["PI009"]["injection_parameters"]["service_code_frequency_limits"]
    pi009_candidates: list[tuple[dict[str, Any], dict[str, Any], int, int]] = []
    for header in headers:
        claim_id = header["claim_id"]
        if (
            claim_id in excluded_claims
            or header["claim_status"] not in {"paid", "adjusted"}
            or header["claim_type"] not in {"professional", "outpatient"}
        ):
            continue
        positive_payments = [
            row
            for row in payments_by_claim[claim_id]
            if row["transaction_type"] == "payment"
            and row["signed_transaction_amount"] > 0
        ]
        if not positive_payments:
            continue
        counts = Counter(
            (row["service_code_system"], row["service_code"])
            for row in lines_by_claim[claim_id]
        )
        for line in sorted(
            lines_by_claim[claim_id], key=lambda row: row["line_number"]
        ):
            system_limits = limits.get(line["service_code_system"], {})
            if line["service_code"] in system_limits:
                limit = int(system_limits[line["service_code"]])
                current = counts[(line["service_code_system"], line["service_code"])]
                if current <= limit:
                    pi009_candidates.append((header, line, current, limit))
                    break
    selected_pi009 = sorted(
        pi009_candidates,
        key=lambda item: deterministic_rank(seed, "pi009_target", item[0]["claim_id"]),
    )[:target_count]
    if len(selected_pi009) != target_count:
        raise SyntheticAnomalyError("Insufficient disjoint PI009 targets")

    selected_claims: set[str] = set()
    for header, source_line, current, limit in selected_pi009:
        claim_id = header["claim_id"]
        selected_claims.add(claim_id)
        injection_id = f"INJ{next_injection:010d}"
        next_injection += 1
        insert_count = limit - current + 1
        exposure = Decimal("0.00")
        first_line_id = None
        for _ in range(insert_count):
            inserted = dict(source_line)
            inserted["claim_line_id"] = f"LIN{next_line:012d}"
            next_line += 1
            inserted["line_number"] = (
                max(row["line_number"] for row in lines_by_claim[claim_id]) + 1
            )
            lines.append(inserted)
            lines_by_claim[claim_id].append(inserted)
            first_line_id = first_line_id or inserted["claim_line_id"]
            net_paid = inserted["allowed_amount"] - inserted["member_liability_amount"]
            exposure += net_paid
            for column, value in inserted.items():
                add_change(
                    injection_id,
                    "insert",
                    "claim_line",
                    inserted["claim_line_id"],
                    column,
                    None,
                    value,
                    column in {"service_code_system", "service_code"},
                )
            for header_column, line_column in (
                ("total_charge_amount", "charge_amount"),
                ("total_allowed_amount", "allowed_amount"),
                ("total_member_liability_amount", "member_liability_amount"),
            ):
                before = header[header_column]
                header[header_column] += inserted[line_column]
                add_change(
                    injection_id,
                    "update",
                    "claim_header",
                    claim_id,
                    header_column,
                    before,
                    header[header_column],
                    False,
                )
        payment = next(
            row
            for row in payments_by_claim[claim_id]
            if row["transaction_type"] == "payment"
            and row["signed_transaction_amount"] > 0
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
        injections.append(
            {
                "injection_id": injection_id,
                "rule_id": "PI009",
                "target_table": "claim_line",
                "target_record_id": first_line_id,
                "claim_id": claim_id,
                "claim_line_id": first_line_id,
                "payment_transaction_id": payment["payment_transaction_id"],
                "provider_id": header["billing_provider_id"],
                "reporting_period": header["service_from_date"].replace(day=1),
                "injection_method": scenarios["PI009"]["injection_method"],
                "label_scope": scenarios["PI009"]["label_scope"],
                "overlap_group": None,
                "expected_financial_exposure": exposure,
                "deterministic_seed": seed,
                "contract_version": anomaly_contract["contract_version"],
                "synthetic_record": True,
            }
        )

    parameters = scenarios["PI010"]["injection_parameters"]
    diagnosis_category = {
        code: category
        for category, codes in parameters["diagnosis_categories"].items()
        for code in codes
    }
    procedure_categories = parameters["procedure_categories"]
    compatible = parameters["compatible_diagnosis_categories"]
    replacements = parameters["incompatible_replacement_codes"]
    pi010_candidates: list[tuple[dict[str, Any], str]] = []
    for header in headers:
        claim_id = header["claim_id"]
        if (
            claim_id in excluded_claims | selected_claims
            or header["claim_status"] not in {"paid", "adjusted"}
            or header["claim_type"] not in {"professional", "inpatient", "outpatient"}
        ):
            continue
        categories = {
            procedure_categories.get(row["service_code_system"], {}).get(
                row["service_code"]
            )
            for row in lines_by_claim[claim_id]
        }
        if len(categories) != 1 or None in categories:
            continue
        procedure_category = categories.pop()
        replacement = replacements.get(procedure_category)
        if replacement is None:
            continue
        replacement_category = diagnosis_category[replacement]
        if replacement_category not in compatible[procedure_category]:
            pi010_candidates.append((header, replacement))
    selected_pi010 = sorted(
        pi010_candidates,
        key=lambda item: deterministic_rank(seed, "pi010_target", item[0]["claim_id"]),
    )[:target_count]
    if len(selected_pi010) != target_count:
        raise SyntheticAnomalyError("Insufficient disjoint PI010 targets")
    for header, replacement in selected_pi010:
        injection_id = f"INJ{next_injection:010d}"
        next_injection += 1
        before = header["principal_diagnosis_code"]
        header["principal_diagnosis_code"] = replacement
        add_change(
            injection_id,
            "update",
            "claim_header",
            header["claim_id"],
            "principal_diagnosis_code",
            before,
            replacement,
            True,
        )
        injections.append(
            {
                "injection_id": injection_id,
                "rule_id": "PI010",
                "target_table": "claim_header",
                "target_record_id": header["claim_id"],
                "claim_id": header["claim_id"],
                "claim_line_id": None,
                "payment_transaction_id": None,
                "provider_id": header["billing_provider_id"],
                "reporting_period": header["service_from_date"].replace(day=1),
                "injection_method": scenarios["PI010"]["injection_method"],
                "label_scope": scenarios["PI010"]["label_scope"],
                "overlap_group": None,
                "expected_financial_exposure": Decimal("0.00"),
                "deterministic_seed": seed,
                "contract_version": anomaly_contract["contract_version"],
                "synthetic_record": True,
            }
        )

    extended = {name: [dict(row) for row in rows] for name, rows in stage.items()}
    extended["claim_header"] = headers
    extended["claim_line"] = lines
    extended["payment_transaction"] = payments
    return extended, injections, changes


def validate_procedure_clinical_anomalies(
    before_stage: dict[str, list[dict[str, Any]]],
    extended: dict[str, list[dict[str, Any]]],
    injections: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    anomaly_contract: dict[str, Any],
) -> dict[str, bool]:
    """Validate final PI009 and PI010 semantics and isolation."""
    target_count = int(anomaly_contract["scenario_defaults"]["target_count"])
    scenarios = {row["rule_id"]: row for row in anomaly_contract["scenarios"]}
    headers = {row["claim_id"]: row for row in extended["claim_header"]}
    before_headers = {row["claim_id"]: row for row in before_stage["claim_header"]}
    before_lines = {row["claim_line_id"]: row for row in before_stage["claim_line"]}
    lines_by_claim: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in extended["claim_line"]:
        lines_by_claim[row["claim_id"]].append(row)
    payment_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in extended["payment_transaction"]:
        payment_totals[row["claim_id"]] += row["signed_transaction_amount"]
    pi009 = [row for row in injections if row["rule_id"] == "PI009"]
    pi010 = [row for row in injections if row["rule_id"] == "PI010"]
    pi009_ids = {row["injection_id"] for row in pi009}
    inserted_line_ids = {
        row["target_record_id"]
        for row in changes
        if row["injection_id"] in pi009_ids
        and row["target_table"] == "claim_line"
        and row["column_name"] == "claim_line_id"
        and row["field_operation"] == "insert"
    }
    limits = scenarios["PI009"]["injection_parameters"]["service_code_frequency_limits"]
    parameters = scenarios["PI010"]["injection_parameters"]
    diagnosis_category = {
        code: category
        for category, codes in parameters["diagnosis_categories"].items()
        for code in codes
    }
    procedure_categories = parameters["procedure_categories"]
    compatible = parameters["compatible_diagnosis_categories"]
    line_totals: dict[str, list[Decimal]] = defaultdict(
        lambda: [Decimal("0.00"), Decimal("0.00"), Decimal("0.00")]
    )
    for row in extended["claim_line"]:
        totals = line_totals[row["claim_id"]]
        totals[0] += row["charge_amount"]
        totals[1] += row["allowed_amount"]
        totals[2] += row["member_liability_amount"]
    prior_claims = {
        row["claim_id"]
        for row in injections
        if row["rule_id"] not in PROCEDURE_CLINICAL_RULES
    }
    pi009_claims = {row["claim_id"] for row in pi009}
    pi010_claims = {row["claim_id"] for row in pi010}
    return {
        "total_injection_count": len(injections) == target_count * 10,
        "pi009_count": len(pi009) == target_count,
        "pi010_count": len(pi010) == target_count,
        "prior_counts_preserved": all(
            sum(row["rule_id"] == f"PI{index:03d}" for row in injections)
            == target_count
            for index in range(1, 9)
        ),
        "targets_disjoint": pi009_claims.isdisjoint(pi010_claims)
        and pi009_claims.isdisjoint(prior_claims)
        and pi010_claims.isdisjoint(prior_claims),
        "injection_ids_unique": len(injections)
        == len({row["injection_id"] for row in injections}),
        "line_ids_unique": len(extended["claim_line"])
        == len({row["claim_line_id"] for row in extended["claim_line"]}),
        "pi009_frequency_above_limit": all(
            (
                lambda target_line: (
                    sum(
                        row["service_code_system"] == target_line["service_code_system"]
                        and row["service_code"] == target_line["service_code"]
                        for row in lines_by_claim[item["claim_id"]]
                    )
                    > int(
                        limits[target_line["service_code_system"]][
                            target_line["service_code"]
                        ]
                    )
                )
            )(
                next(
                    row
                    for row in lines_by_claim[item["claim_id"]]
                    if row["claim_line_id"] == item["claim_line_id"]
                )
            )
            for item in pi009
        ),
        "pi009_inserted_lines_present": bool(inserted_line_ids),
        "pi009_reconciliation": all(
            line_totals[item["claim_id"]]
            == [
                headers[item["claim_id"]]["total_charge_amount"],
                headers[item["claim_id"]]["total_allowed_amount"],
                headers[item["claim_id"]]["total_member_liability_amount"],
            ]
            and payment_totals[item["claim_id"]]
            == headers[item["claim_id"]]["total_allowed_amount"]
            - headers[item["claim_id"]]["total_member_liability_amount"]
            for item in pi009
        ),
        "pi009_positive_exposure": all(
            row["expected_financial_exposure"] > 0 for row in pi009
        ),
        "pi010_incompatible": all(
            all(
                diagnosis_category[
                    headers[item["claim_id"]]["principal_diagnosis_code"]
                ]
                not in compatible[
                    procedure_categories[row["service_code_system"]][
                        row["service_code"]
                    ]
                ]
                for row in lines_by_claim[item["claim_id"]]
            )
            for item in pi010
        ),
        "pi010_zero_exposure": all(
            row["expected_financial_exposure"] == 0 for row in pi010
        ),
        "pi010_only_diagnosis_changed": all(
            {
                **before_headers[claim_id],
                "principal_diagnosis_code": headers[claim_id][
                    "principal_diagnosis_code"
                ],
            }
            == headers[claim_id]
            for claim_id in pi010_claims
        ),
        "preexisting_lines_unchanged": all(
            row
            == next(
                item
                for item in extended["claim_line"]
                if item["claim_line_id"] == line_id
            )
            for line_id, row in before_lines.items()
        ),
        "unchanged_tables_preserved": all(
            extended[name] == before_stage[name]
            for name in before_stage
            if name not in PROCEDURE_CLINICAL_CHANGED_TABLES
        ),
        "all_injections_have_lineage": {row["injection_id"] for row in injections}
        == {row["injection_id"] for row in changes},
    }
