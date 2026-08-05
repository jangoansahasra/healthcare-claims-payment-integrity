# Trusted Claims Dimensional Model

## Purpose

M04 converts the governed operational tables into a compact analytics model for
payment integrity, cost intelligence, policy analysis, and BI. The versioned
contract is `config/trusted_claims_contract.yml`.

The model consumes the isolated anomalous evaluation dataset by default. Every
row retains its synthetic business identifier and source variant. The clean M02
baseline remains immutable.

## Model structure

Five conformed dimensions provide reusable descriptive context:

- `dim_member`
- `dim_provider`
- `dim_plan`
- `dim_date`
- `dim_service`

Five facts preserve operational and financial grains:

- `fact_membership_month`
- `fact_claim`
- `fact_claim_line`
- `fact_payment_transaction`
- `fact_claim_review`

Two bridges retain policy and evaluation relationships:

- `bridge_provider_policy`
- `bridge_claim_anomaly`

## Claim-version semantics

`fact_claim` contains every claim version. Exactly one row per
`logical_claim_id` is marked `is_current_version = true`, using the maximum
version number. Financial and utilization reporting defaults to current
versions so adjustments are not double counted. Operational history can use
all versions when that scope is stated explicitly.

Prior versions remain linked through both `prior_claim_id` and
`prior_claim_key`.

## Financial semantics

Claim charge, allowed, and member-liability totals reconcile to grouped claim
lines. Claim net paid is derived exclusively from the append-only signed
payment ledger. Payments are positive, reversals are negative, and adjustments
retain their governed sign.

Claim-line `plan_paid_amount` is an analytical measure equal to allowed amount
less member liability. It is not substituted for ledger-derived claim net paid.

## Keys and dates

Every table receives a deterministic integer surrogate key generated from its
stably sorted business key. Unresolved foreign keys fail the build; unknown
dimension members are not silently inserted.

The date dimension supports explicit service, service-through, receipt,
adjudication, payment, coverage, review, and policy-assignment roles. No generic
or unnamed claim date is permitted.

## Ground-truth boundary

M03 labels appear only in `bridge_claim_anomaly`. The bridge exists for M05
precision, recall, and exposure evaluation and is prohibited from ordinary
feature sets. Neither `fact_claim` nor `fact_claim_line` contains rule IDs,
labels, or expected anomaly exposure.

## Governance and publication

All records and identities are synthetic. Full curated Parquet is written under
the Git-ignored `data/curated/trusted_claims/` tree. Only small synthetic samples,
contract metadata, and quality reports may be published.

## Production result

The deterministic production build contains:

- 10,000 members, 200 providers, 4 plans, 594 dates, and 20 services;
- 158,746 membership months;
- 77,095 claim versions, including 73,606 current claims;
- 182,348 claim lines and 71,072 payment transactions;
- 3,748 review episodes and 200 provider policy assignments;
- all 500 M03 anomaly labels in the evaluation-only bridge.

The twelve compressed Parquet tables occupy approximately 8.7 MiB. All 67
machine-readable key, schema, row-count, version, financial, eligibility,
policy, and evaluation-boundary checks pass.
