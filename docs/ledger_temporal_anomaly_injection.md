# Payment-Ledger and Temporal Anomaly Injection

## Purpose

This M03 stage deterministically rebuilds the prior PI001/PI002/PI005/PI006
output and extends it with PI003 unresolved payments after reversal and PI004
impossible payment dates. Rebuilding the prerequisite stage prevents duplicate
transactions when the command is rerun.

Run the composed build with:

```bash
python -m src.synthetic.build_ledger_temporal_anomalies
```

## PI003 ledger semantics

For each of 50 eligible positive payments, the build retains the original
transaction and appends:

1. a full negative reversal referencing the original payment; and
2. a positive repayment equal to 40% of the original amount.

Transaction sequence numbers are 1, 2, and 3, and dates increase with the
sequence. The positive repayment remains unresolved and is the governed
expected exposure. Aggregate PI003 exposure is $95,057.12.

## PI004 temporal semantics

For 50 separate eligible payments, only `transaction_date` is changed. The
anomalous date is one day before the linked claim's service-from date. Payment
amounts and adjudicated values are unchanged. PI004 exposure is explicitly zero
because impossible timing alone does not establish a deterministic overpayment.

## Composition and ground truth

The extended dataset contains 300 injections:

- 50 each for PI001, PI002, PI003, PI004, PI005, and PI006;
- 2,450 field-level change records;
- 100 additional payment transactions from 50 reversal/repayment pairs.

PI003 and PI004 targets do not overlap each other or the existing 200 claims.
The builder preserves globally unique injection and transaction identifiers and
rewrites the combined ground-truth Parquet atomically.

The machine-readable report is
`data/metadata/quality/ledger_temporal_anomaly_injection.json`. Dedicated
synthetic-only samples expose the new PI003/PI004 injection and field-change
rows rather than repeating only the earlier scenario group.

## Validation and governance

All 26 stage checks pass, including reversal linkage, full reversal amounts,
monotonic sequences, unresolved net payment, impossible dates, unchanged PI004
amounts, target disjointness, prior-label preservation, complete lineage,
baseline immutability, and repeatable output bytes.

All targets remain synthetic. A temporal or ledger label is controlled
evaluation truth and is not evidence of fraud or a finding about a real entity.
