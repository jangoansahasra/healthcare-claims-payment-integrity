# Synthetic Review, Audit, and Recovery Workflow

## Purpose

This final M02 generator completes the operational baseline with deterministic
claim reviews, audit outcomes, and the governed recovery ledger. It also runs
end-to-end contract and reconciliation checks across all 14 synthetic tables.

Run the complete build sequence with:

```bash
python -m src.synthetic.build_synthetic_dimensions
python -m src.synthetic.build_synthetic_claims
python -m src.synthetic.build_synthetic_workflow
```

## Clean-baseline workflow

Five percent of adjudicated claims are deterministically selected for routine
quality review. Every selected review reaches `completed` status and has exactly
one audit outcome. Review selection follows adjudication and completion follows
selection.

The production build generated:

| Table | Rows | Meaning |
|---|---:|---|
| `claim_review` | 3,748 | Completed routine post-adjudication reviews |
| `audit_outcome` | 3,748 | Clean audit decisions linked one-to-one to reviews |
| `recovery_transaction` | 0 | Typed recovery ledger with no M02 recoveries |

Audit outcomes comprise 3,140 `no_issue` and 608 `inconclusive` results. Every
confirmed amount is zero.

## Recovery decision

M02 intentionally emits an empty recovery table because the clean baseline has
no confirmed improper-payment finding. The Parquet file retains the complete
contract-derived schema, so downstream pipelines can consume it without special
schema handling.

Confirmed overpayments, recovery amounts, and ground-truth anomaly labels are
introduced only in M03. This prevents ordinary review selection from being
misrepresented as evidence of fraud or improper payment.

## End-to-end controls

The machine-readable operational report validates:

- schemas, grains, keys, and foreign keys for all 14 tables;
- synthetic identifier formats and privacy controls;
- eligibility and provider-contract relationships;
- claim lifecycle and immutable version sequencing;
- header-to-line and payment reconciliation;
- review and audit date sequencing;
- one audit per completed review;
- clean audit outcome domains and zero confirmed amounts;
- the typed empty recovery ledger;
- deterministic content hashes for every table.

All 113 operational checks pass. Full Parquet outputs remain under
`data/generated/synthetic/` and outside Git. Synthetic-only samples and the
quality report at `data/metadata/quality/synthetic_operational_baseline.json`
are committed for inspection.
