# Record-Level Anomaly Injection

## Purpose

This M03 increment clones the 14-table clean M02 operational baseline and
injects four controlled record-level scenarios: PI001, PI002, PI005, and PI006.
The clean source Parquet files are never edited.

Run the governed build with:

```bash
python -m src.synthetic.build_record_level_anomalies
```

## Injected scenarios

| Rule | Instances | Intended condition | Expected exposure |
|---|---:|---|---:|
| PI001 | 50 | Exact duplicate claim line | $44,821.43 |
| PI002 | 50 | Near-duplicate claim line | $158,584.83 |
| PI005 | 50 | Header allowed total differs from line sum | $500.00 |
| PI006 | 50 | Net payment exceeds allowed less liability | $500.00 |

All 200 target claims are distinct. No overlap group is used in this increment.

## Scenario isolation

PI001 and PI002 insert new line identifiers and line numbers. Corresponding
header totals and payment amounts are also updated, preserving ordinary
header-line and payment reconciliation. Their only intended integrity condition
is duplicate or near-duplicate service behavior.

PI005 increases only the header allowed total by $10. Lines and payments remain
unchanged. PI006 changes only the positive payment amount so net payment exceeds
allowed less member liability by $10.

Existing claim-line records remain byte-for-byte equivalent at the row-content
level. Non-targeted headers and payments remain equal to the clean baseline.
All other operational tables retain their original Parquet bytes.

## Ground truth and reproducibility

The build produces:

- 200 `anomaly_injection` rows;
- 1,700 typed `anomaly_field_change` rows;
- 14 `baseline_hash_manifest` rows;
- small synthetic-only samples for all three structures;
- `data/metadata/quality/record_level_anomaly_injection.json`.

Target ranking is derived from the configured seed and claim ID through SHA-256.
Repeated reduced end-to-end builds produce identical anomalous and ground-truth
Parquet bytes.

## Quality and governance

All 29 injection checks pass, including baseline hashes before and after,
initial clone identity, target disjointness, exact and near-duplicate semantics,
scenario-specific reconciliation, unchanged-record comparison, positive
exposure, and typed ground-truth schemas.

All data remains synthetic. The labels measure known injected evaluation truth;
they are not evidence of fraud or findings about real providers.
