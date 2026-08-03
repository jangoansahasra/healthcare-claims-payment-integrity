# Controlled Anomaly Injection Contract

## Purpose

M03 creates a separate anomalous copy of the fully validated M02 synthetic
operational baseline. The clean baseline is never edited in place. Every
insertion or mutation receives explicit machine-readable ground truth.

The contract is defined in `config/anomaly_injection_contract.yml`. This first
M03 increment defines semantics only and injects no anomalies.

## Ground-truth model

Three governed tables support evaluation and reproducibility:

| Table | Grain | Purpose |
|---|---|---|
| `anomaly_injection` | One row per injected anomaly | Rule, target, scope, overlap, seed, and expected exposure |
| `anomaly_field_change` | One row per inserted or changed field | Typed before-and-after mutation lineage |
| `baseline_hash_manifest` | One row per clean M02 table | Row count, content hash, schema hash, and contract version |

Labels support claim, claim-line, payment-transaction, provider, and
provider-period evaluation. Field-change rows distinguish insertions from
updates and identify intentional contract violations.

## Isolation and overlap

Anomalous outputs are written under `data/generated/synthetic_anomalous/`,
separate from the clean `data/generated/synthetic/` baseline. Baseline hashes
are verified before and after injection.

Overlap is prohibited by default. The only contract-permitted multi-label
combinations are PI001 with PI006 and PI007 with PI008, and every allowed
overlap must carry an explicit overlap-group identifier. Scenario precedence
makes deterministic target selection independent of execution order.

## Scenario semantics

The ten governed scenarios cover exact and near duplicates, reversal-ledger
behavior, impossible dates, reconciliation mismatches, excess payment,
provider amount and utilization outliers, excessive procedure repetition, and
diagnosis-procedure incompatibility.

Each scenario declares:

- its target table and business grain;
- insertion, mutation, ledger, temporal, or provider-period method;
- eligible claim or transaction state;
- exclusion rules that prevent accidental contamination;
- the exact intended violation;
- its financial-exposure formula.

Zero-exposure rules identify suspicious integrity conditions without asserting
an overpayment amount. Nonzero exposure represents deterministic synthetic
evaluation truth, not a finding against a real provider.

## Governance

All targets remain synthetic and contain no PHI or real provider identity.
Public CMS records are not anomaly targets. Full anomalous data and ground truth
remain outside Git; only small synthetic demonstration samples may be committed.

M03 labels are designed for later rule-engine recall, precision, and
false-positive measurement. They do not establish fraud.

The first implemented scenario group is documented in
[`record_level_anomaly_injection.md`](record_level_anomaly_injection.md).
The composed payment stage is documented in
[`ledger_temporal_anomaly_injection.md`](ledger_temporal_anomaly_injection.md).
