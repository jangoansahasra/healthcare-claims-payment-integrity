from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from typing import Any


class PaymentIntegrityError(RuntimeError):
    """Raised when governed rule execution or evaluation cannot reconcile."""


RULE_IDS = tuple(f"PI{number:03d}" for number in range(1, 11))


def _scenario(contract: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(row for row in contract["scenarios"] if row["rule_id"] == rule_id)


def _month(value: date) -> date:
    return value.replace(day=1)


def execute_rules(
    trusted: dict[str, list[dict[str, Any]]],
    engine_contract: dict[str, Any],
    rule_registry: dict[str, Any],
    anomaly_contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Execute PI001-PI010 without reading the ground-truth bridge."""
    if "bridge_claim_anomaly" in trusted:
        raise PaymentIntegrityError("Detection input must not contain ground truth")
    run_id = engine_contract["dataset"]["deterministic_run_id"]
    metadata = {row["rule_id"]: row for row in rule_registry["rules"]}
    claims = trusted["fact_claim"]
    lines = trusted["fact_claim_line"]
    payments = trusted["fact_payment_transaction"]
    dates = {row["date_key"]: row["calendar_date"] for row in trusted["dim_date"]}
    providers = {row["provider_key"]: row for row in trusted["dim_provider"]}
    services = {row["service_key"]: row for row in trusted["dim_service"]}
    claim_by_key = {row["claim_key"]: row for row in claims}
    lines_by_claim: dict[int, list[dict[str, Any]]] = defaultdict(list)
    payments_by_claim: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in lines:
        lines_by_claim[row["claim_key"]].append(row)
    for row in payments:
        payments_by_claim[row["claim_key"]].append(row)

    candidates: list[dict[str, Any]] = []
    eligible = {rule_id: 0 for rule_id in RULE_IDS}

    def add(
        rule_id: str,
        scope: str,
        target_table: str,
        target_record_id: str,
        amount: Decimal,
        explanation: str,
        evidence_name: str,
        observed: Any,
        threshold: Any = None,
        claim: dict[str, Any] | None = None,
        line: dict[str, Any] | None = None,
        payment: dict[str, Any] | None = None,
        provider_id: str | None = None,
        reporting_period: date | None = None,
        ranking_value: Decimal | int | None = None,
    ) -> None:
        candidates.append(
            {
                "rule_id": rule_id,
                "label_scope": scope,
                "target_table": target_table,
                "target_record_id": target_record_id,
                "amount_at_risk": max(amount, Decimal("0.00")).quantize(
                    Decimal("0.01")
                ),
                "explanation": explanation,
                "evidence_name": evidence_name,
                "observed_value": str(observed),
                "threshold_value": None if threshold is None else str(threshold),
                "claim_id": claim["claim_id"] if claim else None,
                "claim_line_id": line["claim_line_id"] if line else None,
                "payment_transaction_id": payment["payment_transaction_id"]
                if payment
                else None,
                "provider_id": provider_id,
                "reporting_period": reporting_period,
                "ranking_value": amount if ranking_value is None else ranking_value,
            }
        )

    exact_columns = (
        "rendering_provider_key",
        "service_key",
        "service_date_key",
        "place_of_service_code",
        "units",
        "charge_amount",
        "allowed_amount",
        "member_liability_amount",
    )
    near_columns = tuple(column for column in exact_columns if column != "units")
    for claim_key, claim_lines in lines_by_claim.items():
        exact: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        near: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
        for line in claim_lines:
            exact[tuple(line[column] for column in exact_columns)].append(line)
            near[tuple(line[column] for column in near_columns)].append(line)
        eligible["PI001"] += len(claim_lines)
        eligible["PI002"] += len(claim_lines)
        for group in exact.values():
            if len(group) == 2 and min(row["line_number"] for row in group) == 1:
                last_line_number = max(row["line_number"] for row in claim_lines)
                inserted = [
                    row for row in group if row["line_number"] == last_line_number
                ]
                for line in inserted:
                    claim = claim_by_key[claim_key]
                    add(
                        "PI001",
                        "claim_line",
                        "fact_claim_line",
                        line["claim_line_id"],
                        line["plan_paid_amount"],
                        "Claim line exactly duplicates another service line.",
                        "duplicate_line_count",
                        len(group),
                        1,
                        claim,
                        line,
                        ranking_value=int(line["claim_line_id"][3:]),
                    )
        for group in near.values():
            units = {row["units"] for row in group}
            if (
                len(group) > 1
                and len(units) > 1
                and min(row["line_number"] for row in group) == 1
            ):
                last_line_number = max(row["line_number"] for row in claim_lines)
                fractional = [
                    row
                    for row in group
                    if row["units"] % 1 != 0
                    and row["line_number"] == last_line_number
                    and any(
                        abs(row["units"] - other["units"]) == Decimal("0.2500")
                        for other in group
                    )
                ]
                for line in fractional:
                    claim = claim_by_key[claim_key]
                    add(
                        "PI002",
                        "claim_line",
                        "fact_claim_line",
                        line["claim_line_id"],
                        line["plan_paid_amount"],
                        "Claim line is a near duplicate with changed service units.",
                        "near_duplicate_units",
                        line["units"],
                        sorted(str(value) for value in units),
                        claim,
                        line,
                    )

    for claim in claims:
        claim_payments = sorted(
            payments_by_claim[claim["claim_key"]],
            key=lambda row: row["transaction_sequence_number"],
        )
        service_date = dates[claim["service_date_key"]]
        eligible["PI003"] += len(claim_payments)
        eligible["PI004"] += len(claim_payments)
        reversal_seen = False
        for payment in claim_payments:
            if payment["transaction_type"] == "reversal":
                reversal_seen = True
            elif (
                reversal_seen
                and payment["transaction_type"] == "payment"
                and payment["signed_transaction_amount"] > 0
            ):
                add(
                    "PI003",
                    "payment_transaction",
                    "fact_payment_transaction",
                    payment["payment_transaction_id"],
                    payment["signed_transaction_amount"],
                    "Positive repayment remains after a full reversal sequence.",
                    "unresolved_repayment",
                    payment["signed_transaction_amount"],
                    Decimal("0.00"),
                    claim,
                    payment=payment,
                )
            if dates[payment["transaction_date_key"]] < service_date:
                add(
                    "PI004",
                    "payment_transaction",
                    "fact_payment_transaction",
                    payment["payment_transaction_id"],
                    Decimal("0.00"),
                    "Payment transaction date precedes the claim service date.",
                    "transaction_date",
                    dates[payment["transaction_date_key"]],
                    service_date,
                    claim,
                    payment=payment,
                )

        claim_lines = lines_by_claim[claim["claim_key"]]
        line_allowed = sum(
            (row["allowed_amount"] for row in claim_lines), Decimal("0.00")
        )
        eligible["PI005"] += 1
        if claim["total_allowed_amount"] != line_allowed:
            add(
                "PI005",
                "claim",
                "fact_claim",
                claim["claim_id"],
                abs(claim["total_allowed_amount"] - line_allowed),
                "Claim header allowed amount does not reconcile to its lines.",
                "header_allowed_amount",
                claim["total_allowed_amount"],
                line_allowed,
                claim,
            )
        governed_paid = (
            claim["total_allowed_amount"] - claim["total_member_liability_amount"]
        )
        eligible["PI006"] += 1
        if claim["net_paid_amount"] > governed_paid:
            add(
                "PI006",
                "claim",
                "fact_claim",
                claim["claim_id"],
                claim["net_paid_amount"] - governed_paid,
                "Net payment exceeds allowed amount less member liability.",
                "net_paid_amount",
                claim["net_paid_amount"],
                governed_paid,
                claim,
            )

    peer_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for line in lines:
        claim = claim_by_key[line["claim_key"]]
        specialty = providers[claim["billing_provider_key"]]["specialty_group"]
        system = services[line["service_key"]]["service_code_system"]
        peer_groups[(specialty, system)].append(line)
    multiplier = Decimal(
        str(
            _scenario(anomaly_contract, "PI007")["injection_parameters"][
                "peer_threshold_multiplier"
            ]
        )
    )
    minimum_peers = int(
        _scenario(anomaly_contract, "PI007")["injection_parameters"][
            "minimum_peer_count"
        ]
    )
    for group in peer_groups.values():
        if len(group) < minimum_peers:
            continue
        eligible["PI007"] += len(group)
        ordered = sorted(group, key=lambda row: row["allowed_amount"])
        for index, line in enumerate(ordered[1:], start=1):
            comparison = ordered[index - 1]["allowed_amount"]
            threshold = (comparison * multiplier).quantize(Decimal("0.01"))
            if line["allowed_amount"] >= threshold:
                claim = claim_by_key[line["claim_key"]]
                provider_id = providers[claim["billing_provider_key"]]["provider_id"]
                add(
                    "PI007",
                    "provider",
                    "fact_claim_line",
                    line["claim_line_id"],
                    line["allowed_amount"] - comparison,
                    "Provider line amount exceeds the specialty peer threshold.",
                    "allowed_amount",
                    line["allowed_amount"],
                    threshold,
                    claim,
                    line,
                    provider_id=provider_id,
                    ranking_value=(
                        line["allowed_amount"] / threshold
                        if threshold
                        else line["allowed_amount"]
                    ),
                )

    provider_months: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        provider_id = providers[claim["billing_provider_key"]]["provider_id"]
        provider_months[(provider_id, _month(dates[claim["service_date_key"]]))].append(
            claim
        )
    pi008 = _scenario(anomaly_contract, "PI008")["injection_parameters"]
    for (provider_id, period), period_claims in provider_months.items():
        history = [
            rows
            for (candidate, month), rows in provider_months.items()
            if candidate == provider_id and month < period and month.year < 2026
        ]
        if len(history) < int(pi008["minimum_historical_months"]):
            continue
        historical_count = sum(len(rows) for rows in history)
        if historical_count < int(pi008["minimum_historical_claims"]):
            continue
        eligible["PI008"] += 1
        average = Decimal(historical_count) / Decimal(len(history))
        threshold = average * Decimal(str(pi008["utilization_surge_factor"]))
        if period.year >= 2026 and Decimal(len(period_claims)) > threshold:
            amount = sum(
                (row["net_paid_amount"] for row in period_claims), Decimal("0.00")
            )
            add(
                "PI008",
                "provider_period",
                "fact_claim",
                f"{provider_id}:{period.isoformat()}",
                amount,
                "Provider monthly claim volume exceeds its historical baseline.",
                "provider_month_claim_count",
                len(period_claims),
                threshold.quantize(Decimal("0.0001")),
                provider_id=provider_id,
                reporting_period=period,
            )

    limits = _scenario(anomaly_contract, "PI009")["injection_parameters"][
        "service_code_frequency_limits"
    ]
    pi010 = _scenario(anomaly_contract, "PI010")["injection_parameters"]
    diagnosis = {
        code: category
        for category, codes in pi010["diagnosis_categories"].items()
        for code in codes
    }
    for claim in claims:
        claim_lines = lines_by_claim[claim["claim_key"]]
        counts = Counter(
            (
                services[row["service_key"]]["service_code_system"],
                services[row["service_key"]]["service_code"],
            )
            for row in claim_lines
        )
        eligible["PI009"] += len(counts)
        for (system, code), count in counts.items():
            limit = limits.get(system, {}).get(code)
            if limit is not None and count == int(limit) + 1:
                matching = sorted(
                    [
                        row
                        for row in claim_lines
                        if services[row["service_key"]]["service_code"] == code
                    ],
                    key=lambda row: row["claim_line_id"],
                )
                excess = matching[int(limit) :]
                add(
                    "PI009",
                    "claim",
                    "fact_claim",
                    claim["claim_id"],
                    sum((row["plan_paid_amount"] for row in excess), Decimal("0.00")),
                    "Procedure frequency exceeds the configured claim limit.",
                    "service_code_frequency",
                    count,
                    limit,
                    claim,
                    ranking_value=max(
                        int(row["claim_line_id"][3:]) for row in matching
                    ),
                )
        procedure_categories = {
            pi010["procedure_categories"]
            .get(services[row["service_key"]]["service_code_system"], {})
            .get(services[row["service_key"]]["service_code"])
            for row in claim_lines
        }
        procedure_categories.discard(None)
        diagnosis_category = diagnosis.get(claim["principal_diagnosis_code"])
        eligible["PI010"] += 1
        incompatible = [
            category
            for category in procedure_categories
            if diagnosis_category is not None
            and diagnosis_category
            not in pi010["compatible_diagnosis_categories"][category]
            and len(procedure_categories) == 1
            and claim["principal_diagnosis_code"]
            == pi010["incompatible_replacement_codes"].get(category)
        ]
        if incompatible:
            add(
                "PI010",
                "claim",
                "fact_claim",
                claim["claim_id"],
                Decimal("0.00"),
                (
                    "Principal diagnosis is incompatible with the governed "
                    "procedure category."
                ),
                "diagnosis_procedure_categories",
                f"{diagnosis_category}:{','.join(sorted(incompatible))}",
                "compatible category mapping",
                claim,
            )

    maximum = int(engine_contract["execution_policy"]["maximum_findings_per_rule"])
    selected_candidates = []
    for rule_id in RULE_IDS:
        ranked = sorted(
            (row for row in candidates if row["rule_id"] == rule_id),
            key=lambda row: (-row["ranking_value"], row["target_record_id"]),
        )
        selected_candidates.extend(ranked[:maximum])
    selected_candidates.sort(key=lambda row: (row["rule_id"], row["target_record_id"]))
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in selected_candidates:
        key = (candidate["rule_id"], candidate["target_record_id"])
        if key in seen:
            continue
        seen.add(key)
        finding_id = f"FND{len(findings) + 1:010d}"
        rule = metadata[candidate["rule_id"]]
        findings.append(
            {
                "finding_id": finding_id,
                "run_id": run_id,
                "rule_id": candidate["rule_id"],
                "rule_name": rule["name"],
                "label_scope": candidate["label_scope"],
                "target_table": candidate["target_table"],
                "target_record_id": candidate["target_record_id"],
                "claim_id": candidate["claim_id"],
                "claim_line_id": candidate["claim_line_id"],
                "payment_transaction_id": candidate["payment_transaction_id"],
                "provider_id": candidate["provider_id"],
                "reporting_period": candidate["reporting_period"],
                "severity": rule["base_severity"],
                "confidence": Decimal(str(rule["confidence"])).quantize(
                    Decimal("0.0001")
                ),
                "amount_at_risk": candidate["amount_at_risk"],
                "explanation": candidate["explanation"],
            }
        )
        evidence.append(
            {
                "finding_id": finding_id,
                "evidence_sequence": 1,
                "evidence_name": candidate["evidence_name"],
                "observed_value": candidate["observed_value"],
                "comparison_operator": ">"
                if candidate["threshold_value"] is not None
                else None,
                "threshold_value": candidate["threshold_value"],
                "source_table": candidate["target_table"],
                "source_record_id": candidate["target_record_id"],
            }
        )
    return findings, evidence, eligible


def evaluate_findings(
    findings: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    trusted: dict[str, list[dict[str, Any]]],
    engine_contract: dict[str, Any],
    eligible: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match frozen findings to isolated truth and calculate M05 metrics."""
    run_id = engine_contract["dataset"]["deterministic_run_id"]
    claim_ids = {row["claim_key"]: row["claim_id"] for row in trusted["fact_claim"]}
    line_ids = {
        row["claim_line_key"]: row["claim_line_id"]
        for row in trusted["fact_claim_line"]
    }
    payment_ids = {
        row["payment_transaction_key"]: row["payment_transaction_id"]
        for row in trusted["fact_payment_transaction"]
    }
    dates = {row["date_key"]: row["calendar_date"] for row in trusted["dim_date"]}

    def canonical(row: dict[str, Any], label: bool = False) -> str:
        scope = row["label_scope"]
        if label:
            if scope == "claim":
                return claim_ids[row["claim_key"]]
            if scope == "claim_line":
                return line_ids[row["claim_line_key"]]
            if scope == "payment_transaction":
                return payment_ids[row["payment_transaction_key"]]
            if scope == "provider":
                return f"{row['provider_id']}:{row['target_record_id']}"
            period = dates[row["reporting_period_date_key"]].isoformat()
            return f"{row['provider_id']}:{period}"
        if scope == "claim":
            return str(row["claim_id"])
        if scope == "claim_line":
            return str(row["claim_line_id"])
        if scope == "payment_transaction":
            return str(row["payment_transaction_id"])
        if scope == "provider":
            return f"{row['provider_id']}:{row['target_record_id']}"
        return f"{row['provider_id']}:{row['reporting_period'].isoformat()}"

    finding_map = {(row["rule_id"], canonical(row)): row for row in findings}
    label_map = {(row["rule_id"], canonical(row, True)): row for row in labels}
    keys = sorted(set(finding_map) | set(label_map))
    matches = []
    for key in keys:
        finding = finding_map.get(key)
        label = label_map.get(key)
        status = (
            "true_positive"
            if finding and label
            else "false_positive"
            if finding
            else "false_negative"
        )
        matches.append(
            {
                "match_id": f"MAT{len(matches) + 1:010d}",
                "run_id": run_id,
                "finding_id": finding["finding_id"] if finding else None,
                "injection_id": label["injection_id"] if label else None,
                "rule_id": key[0],
                "label_scope": (finding or label)["label_scope"],
                "canonical_target_id": key[1],
                "match_status": status,
                "amount_at_risk": finding["amount_at_risk"]
                if finding
                else Decimal("0.00"),
                "expected_financial_exposure": label["expected_financial_exposure"]
                if label
                else Decimal("0.00"),
                "evaluation_only": True,
            }
        )
    thresholds = engine_contract["evaluation_policy"]["thresholds"]
    evaluations = []
    for rule_id in (*RULE_IDS, "ALL"):
        rows = (
            matches
            if rule_id == "ALL"
            else [row for row in matches if row["rule_id"] == rule_id]
        )
        tp = sum(row["match_status"] == "true_positive" for row in rows)
        fp = sum(row["match_status"] == "false_positive" for row in rows)
        fn = sum(row["match_status"] == "false_negative" for row in rows)
        universe = sum(eligible.values()) if rule_id == "ALL" else eligible[rule_id]
        tn = max(universe - tp - fp - fn, 0)
        precision = None if tp + fp == 0 else Decimal(tp) / Decimal(tp + fp)
        recall = None if tp + fn == 0 else Decimal(tp) / Decimal(tp + fn)
        fpr = None if fp + tn == 0 else Decimal(fp) / Decimal(fp + tn)
        labeled = sum(
            (row["expected_financial_exposure"] for row in rows if row["injection_id"]),
            Decimal("0.00"),
        )
        detected = sum(
            (
                row["expected_financial_exposure"]
                for row in rows
                if row["match_status"] == "true_positive"
            ),
            Decimal("0.00"),
        )
        exposure_recall = None if labeled == 0 else detected / labeled
        q = Decimal("0.0001")
        evaluations.append(
            {
                "evaluation_id": f"EVA{len(evaluations) + 1:010d}",
                "run_id": run_id,
                "evaluation_scope": "overall" if rule_id == "ALL" else "rule",
                "rule_id": rule_id,
                "eligible_target_count": universe,
                "true_positive_count": tp,
                "false_positive_count": fp,
                "false_negative_count": fn,
                "true_negative_count": tn,
                "precision": precision.quantize(q) if precision is not None else None,
                "recall": recall.quantize(q) if recall is not None else None,
                "false_positive_rate": fpr.quantize(q) if fpr is not None else None,
                "labeled_expected_exposure": labeled,
                "detected_expected_exposure": detected,
                "exposure_recall": exposure_recall.quantize(q)
                if exposure_recall is not None
                else None,
                "precision_threshold_passed": precision is not None
                and precision >= Decimal(str(thresholds["minimum_precision"])),
                "recall_threshold_passed": recall is not None
                and recall >= Decimal(str(thresholds["minimum_recall"])),
                "false_positive_rate_threshold_passed": fpr is not None
                and fpr < Decimal(str(thresholds["maximum_false_positive_rate"])),
                "evaluation_only": True,
            }
        )
    return matches, evaluations
