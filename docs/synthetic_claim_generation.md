# Synthetic Claim Lifecycle Generation

## Purpose

The M02 claim generator creates a clean operational baseline across professional,
inpatient, outpatient, and pharmacy claims. All identities are synthetic. CMS
sources provide aggregate calibration categories only; no real claim or provider
record is copied.

Run the dimension build first, followed by the claim build:

```bash
python -m src.synthetic.build_synthetic_dimensions
python -m src.synthetic.build_synthetic_claims
```

## Generated lifecycle

| Table | Rows | Operational meaning |
|---|---:|---|
| `claim_header` | 75,000 | Immutable synthetic claim versions |
| `claim_line` | 177,206 | Service-level units and adjudicated amounts |
| `adjudication_event` | 150,000 | Received and final status events |
| `payment_transaction` | 68,877 | Append-only positive clean-baseline payments |
| `denial_outcome` | 6,123 | Ordinary administrative and coverage denials |

The configured claim mix is 52% professional, 10% inpatient, 20% outpatient,
and 18% pharmacy. Actual deterministic counts are recorded in the quality
report. Five percent of eligible records are linked second versions; identity,
service period, and logical claim ID remain stable across versions.

## Financial semantics

- Header charge, allowed, and member-liability totals equal their line sums.
- Allowed amount never exceeds charge in this synthetic clean baseline.
- Member liability never exceeds allowed amount.
- Net insurer payment equals allowed amount less member liability.
- Denied claims have zero allowed amount, zero liability, and no payment.
- Payment records are append-only. Reversal and adjustment behavior remains
  governed for a later clean M02 workflow increment.

Fractional pharmacy units are retained as `DECIMAL(18,4)`. Financial values use
`DECIMAL(18,2)`.

## Relationship and date controls

Every claim is linked to membership active during its service month and to a
provider contracted with the member's plan. Dates follow this ordering:

`service_from <= service_through <= received <= adjudication <= payment`

Second versions are received only after the prior version was adjudicated.
Service and eligibility use the service date, operations use the adjudication
date, and finance uses the transaction date.

## Outputs and governance

Full Zstandard Parquet outputs remain under `data/generated/synthetic/` and are
excluded from Git. Twenty-five-row synthetic-only CSV samples are committed.
The machine-readable report is
`data/metadata/quality/synthetic_claim_lifecycle.json`.

The clean M02 baseline contains no intentional payment-integrity anomaly or
ground-truth anomaly label. Those responsibilities remain isolated to M03.
