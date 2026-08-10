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

## DL-010: SAS execution evidence

The local macOS environment has no SAS executable. M08 may prepare portable
inputs, reference results, contracts, and SAS programs locally, but it remains
not executed until SAS 9.4M7+ or SAS Viya 4 produces a real versioned log.
Python or mocked results cannot be represented as independent SAS validation.

On 2026-08-06, execution `M08_20260806_FINAL` ran in SAS OnDemand for
Academics using SAS 9.4 M8 on Linux. The real log passed the governed scan and
all 181 comparisons passed with no missing SAS values. Full inputs, logs, and
results remain excluded from Git; only checksum-backed evidence is published.

## DL-011: Fabric trial before paid Azure capacity

M09 uses the available university Fabric Free account and an approved 60-day
Fabric trial before considering paid capacity. An active Azure for Students
subscription is available, but no paid M09 resource may be created until an
explicit approval, project budget, alerts, and teardown procedure exist.
Readiness evidence records categorical account status only; user email,
subscription and tenant identifiers, billing identifiers, and unredacted portal
screenshots remain outside Git.
