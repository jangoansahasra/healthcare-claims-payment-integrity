# Synthetic Claim Lifecycle and Reconciliation

## Lifecycle sequence

1. A synthetic member is enrolled in a plan for a coverage month.
2. A provider has an effective contract with the plan where applicable.
3. A claim version and its lines are submitted for covered service dates.
4. Append-only adjudication events record operational state changes.
5. A denial record is created when adjudication produces a denial.
6. Paid claims receive append-only signed financial transactions.
7. Adjustments or resubmissions create a new linked claim version.
8. Reviews and audits retain their own workflow and outcome history.
9. Confirmed amounts may produce append-only recovery transactions.

Historical records are never overwritten.

## Claim versioning

`logical_claim_id` groups all versions of the same operational claim.
`claim_id` identifies one immutable version. Versions above one must reference
`prior_claim_id`, and version numbers increase monotonically. Current-state
views may select the maximum version, but stored history remains intact.

## Financial ledger

The payment transaction table is authoritative for paid amounts:

```text
net paid amount = sum(signed transaction amount)
```

- payments are positive;
- reversals are negative and reference the reversed transaction;
- adjustments are signed according to their financial effect;
- transactions are appended and never updated in place.

Recovery transactions form a separate append-only audit-recovery ledger and do
not rewrite the original claim payment history.

## Date roles

| Reporting purpose | Authoritative date |
|---|---|
| Utilization | Service-from date |
| Eligibility | Service-from date and coverage month |
| Claims operations | Adjudication date |
| Cash and finance | Payment transaction date |

Reports must use named date roles; the model does not expose an ambiguous
generic “claim date.”

## Reconciliation rules

- Header charge equals the sum of line charges.
- Header allowed amount equals the sum of line allowed amounts.
- Header member liability equals the sum of line member liability.
- Current net paid amount equals signed payment-ledger transactions.
- Payment, reversal, and adjustment signs follow their ledger semantics.
- Eligibility covers the service-from date.
- Every claim line references a valid claim version.
- Total recovery cannot exceed the confirmed audit amount.

All monetary values use fixed `DECIMAL(18,2)` precision. Service units use
`DECIMAL(18,4)` so valid fractional units are not truncated.

## Clean-baseline boundary

Ordinary denials, reviews, reversals, and adjustments are valid operational
events and may exist in M02. They are not labeled payment-integrity anomalies.
M03 introduces controlled incorrect-payment scenarios and separate ground-truth
labels without using real provider identities.
