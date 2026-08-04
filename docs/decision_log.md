# Decision Log

## DL-001: Authoritative financial representation

Payments, reversals, and adjustments are stored in an append-only transaction
ledger. Net paid amount is the sum of signed transaction amounts. Compatibility
views may expose separate payment and reversal facts.

## DL-002: Claim history

Adjusted and resubmitted claims create new claim versions linked to the prior
version. Historical operational states are retained.

## DL-003: Date definitions

- Service date drives utilization reporting.
- Payment date drives cash and finance reporting.
- Adjudication date drives claims-operation reporting.
- Power BI exposes explicit date-role measures; no unnamed "claim date" is used.

## DL-004: Historical restatement

Current financial dashboards restate prior periods for newly received
reversals and adjustments. Operational snapshots retain their original state
so users can compare "as reported" with "currently adjudicated."

## DL-005: Duplicate terminology

Rules distinguish exact, probable, and possible duplicates. A flag is an
investigation lead and never a declaration that a claim is fraudulent.

## DL-006: Provider specialization

Provider outlier rules compare providers within specialty, geography, and
procedure category where sample size permits. High utilization alone is not
classified as incorrect.

## DL-007: Privacy threshold

Public report breakdowns are suppressed when fewer than 11 distinct synthetic
members contribute. This is a portfolio control, not a universal legal rule.

## DL-008: Code descriptions

Public ICD-10-CM and HCPCS Level II sources may be used. Proprietary CPT
descriptions will not be redistributed.

## DL-009: Portfolio visualization tools

Looker Studio is the primary six-page portfolio dashboard because it supports
browser-based authoring on macOS and straightforward public demonstration. A
compact Power BI report will independently reproduce selected executive KPIs
to retain Microsoft Fabric and Power BI interoperability evidence without
making Windows-only authoring the critical path.
