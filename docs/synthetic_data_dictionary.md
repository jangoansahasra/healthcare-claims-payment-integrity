# Synthetic Operational Data Dictionary

Generation details are documented in
[`synthetic_dimension_generation.md`](synthetic_dimension_generation.md) and
[`synthetic_claim_generation.md`](synthetic_claim_generation.md).

## Purpose

The M02 synthetic insurer dataset supplies operational records that unrestricted
CMS public-use files do not provide. It contains no real beneficiary or provider
identities and no protected health information. Aggregate CMS distributions
inform calibration, but individual public records are never copied into the
synthetic population.

The authoritative machine-readable contract is
`config/synthetic_data_contract.yml`.

## Dataset controls

| Control | Value |
|---|---|
| Role | Clean operational baseline |
| Reporting period | 2025-01-01 through 2026-06-30 |
| Simulated policy start | 2026-01-01 |
| Deterministic seed | 20260724 |
| Members | 10,000 |
| Plans | 4 |
| Providers | 200 |
| Claim headers | 75,000 |
| Currency | USD |
| Monetary type | `DECIMAL(18,2)` |
| Full output | Local Parquet under `data/generated/synthetic/` |
| Public samples | Small synthetic-only extracts under `data/sample/synthetic/` |

## Table inventory

| Table | Grain | Primary key | Purpose |
|---|---|---|---|
| `member` | One synthetic member | `member_id` | Non-identifying demographic and geographic attributes |
| `plan` | One synthetic benefit plan | `plan_id` | Product and effective-period attributes |
| `provider` | One synthetic provider | `provider_id` | Synthetic specialty, geography, and calibration lineage |
| `provider_contract` | One provider-plan contract period | `contract_id` | Network and reimbursement relationship |
| `membership_month` | One member-plan-month | `member_id`, `plan_id`, `coverage_month` | Service-date eligibility |
| `claim_header` | One claim version | `claim_id` | Claim identity, lifecycle dates, status, and header totals |
| `claim_line` | One claim-version line | `claim_line_id` | Service code, units, and line-level amounts |
| `adjudication_event` | One claim state change | `adjudication_event_id` | Append-only operational history |
| `payment_transaction` | One claim financial transaction | `payment_transaction_id` | Signed payment, reversal, or adjustment ledger |
| `claim_review` | One claim review episode | `review_id` | Selection and review workflow |
| `denial_outcome` | One denied claim version | `denial_id` | Denial reason and amount |
| `policy_assignment` | One provider-policy period | `policy_assignment_id` | Treatment and comparison assignment |
| `audit_outcome` | One completed claim audit | `audit_id` | Confirmed clean-baseline review result |
| `recovery_transaction` | One recovery transaction | `recovery_transaction_id` | Append-only recovery activity |

## Core relationships

- Membership links members to plans by coverage month.
- Contracts link synthetic providers to plans for effective periods.
- Claim headers link members, plans, and synthetic billing/rendering providers.
- Claim lines, adjudication events, payment transactions, denials, and reviews
  reference a specific immutable claim version.
- Audits reference both a review and its claim version.
- Recoveries reference the audit and claim that established the confirmed amount.
- Policy assignments apply to synthetic providers for explicit date ranges.

Every relationship is declared and tested in the YAML contract.

## Identifiers

All identifiers are strings with synthetic prefixes such as `MBR`, `PRV`,
`CLM`, and `PAY`. A logical claim ID groups versions; each claim-version ID
contains its own version suffix. These IDs are generated values and are not
derived from real member IDs, NPIs, claim numbers, or other source identifiers.

## Claim types and codes

The clean baseline supports professional, inpatient, outpatient, and pharmacy
claims. Claim lines carry an explicit code-system field so code values are not
interpreted without context. Public code descriptions may be used where
licensing permits; proprietary CPT descriptions are not redistributed.

## Privacy and anomaly boundary

Public breakdowns require at least 11 distinct synthetic members. Full generated
data remains outside Git. M02 generates ordinary clean operational variation;
the ten intentional anomaly types and complete ground truth are introduced only
in M03.
