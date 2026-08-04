# Procedure-Frequency and Clinical-Compatibility Anomaly Injection

## Scope

This final M03 stage composes PI001–PI008 and appends 50 PI009 excessive
procedure-frequency labels and 50 PI010 diagnosis-procedure incompatibility
labels. The completed anomalous dataset contains 500 deterministic labels—50
for each governed payment-integrity rule.

## PI009 repeated procedure above limit

The contract defines explicit per-claim frequency ceilings for supported HCPCS
and APC codes. Eligible paid or adjusted professional and outpatient claims are
selected without overlap with prior targets. The injector copies a governed
source line until the claim/service-code count exceeds its ceiling.

Inserted lines receive unique identifiers and complete field lineage. Claim
header totals and the positive payment transaction are updated by the inserted
amounts, preserving header-line and payment reconciliation. Expected exposure
is the sum of inserted allowed amounts less member liability.

## PI010 diagnosis-procedure incompatibility

The contract maps the small synthetic diagnosis and procedure domains to
explicit categories. Eligible paid or adjusted claims with a single governed
procedure category receive a deterministic diagnosis code from an incompatible
category.

Only `principal_diagnosis_code` changes. Lines, adjudication events, payments,
and financial totals remain byte-equivalent to their input stage. PI010 has
zero expected exposure because incompatibility is a review signal rather than
proof of an overpayment.

## Results and reproducibility

The production result contains 500 anomaly labels, 145,547 field-change rows,
and the unchanged 14-table M02 baseline hash manifest. All 24 final-stage
quality checks pass. PI009 exposure is $78,308.43 and PI010 exposure is $0.00.

Focused tests verify deterministic injection semantics. A composed integration
test rebuilds the entire PI001–PI010 chain twice and compares content hashes and
Parquet bytes for every changed table and ground-truth output.

## Governance

All claims, members, providers, diagnoses, and targets are synthetic. The
category mappings and frequency limits are controlled evaluation conventions,
not clinical guidance, production payment policy, or evidence of fraud. Public
CMS records remain aggregate calibration inputs only and are never labeled.
