# Microsoft Fabric and Azure Deployment Contract

## Purpose

M09 demonstrates that the locally governed synthetic analytics can be loaded,
queried, refreshed, and reconciled in Microsoft Fabric without changing their
business definitions. This contract-first increment does not activate a trial,
create a workspace, upload data, or provision paid Azure resources.

## Verified readiness

Readiness was checked interactively on 2026-08-09. The university tenant allows
access to the Fabric portal with a Free license and displays an available
60-day trial offer, but that trial is not active. An active Azure for Students
subscription is available with Owner access. No M09 resource has been created.

The evidence intentionally records only categorical status. Email addresses,
subscription and tenant identifiers, billing identifiers, tokens, and unredacted
screenshots are prohibited from Git and execution logs.

## Planned cloud architecture

The deployment uses one portfolio workspace, one Lakehouse, one load-and-check
notebook, and one orchestration pipeline. Local curated Parquet files land in
the Lakehouse `Files/landing` area and are materialized as governed Delta tables
under `Tables`. The Lakehouse SQL analytics endpoint is the read-only query
surface for the later Power BI validation report.

The authoritative schemas remain the existing M04-M07 contracts. M09 cannot
silently change columns, types, grain, keys, financial definitions, or date
roles. Service-period analytics and payment-period cash flow remain separate.

## Analytical boundaries

- Trusted claims, cost intelligence, and policy outputs are analytical surfaces.
- Payment-integrity findings are explainable review leads, not fraud findings.
- `bridge_claim_anomaly`, `finding_ground_truth_match`, and `rule_evaluation`
  are restricted evaluation tables and are not ordinary analytical features.
- All records, providers, members, assignments, and outcomes are synthetic.

## Reconciliation

Every cloud table must match its local source at row-count and distinct-primary-
key grain with zero tolerance. Governed financial totals must match within
$0.01. The deployment also checks eligible member months, amount at risk,
provider-month panel counts, input SHA-256 hashes, foreign keys, and the
separation of service-date and payment-date reporting.

Cloud success cannot be claimed from screenshots alone. It requires a real
workspace, capacity and region, notebook and pipeline run identifiers, artifact
hashes, machine-readable reconciliation results, redacted evidence, and recorded
teardown and final-cost status.

## Cost and security controls

The Fabric trial is preferred. Activation occurs only after this contract is
merged and the region is confirmed. Any paid Azure provisioning requires
separate explicit approval plus a budget and 50%, 80%, and 100% alerts. Only one
demo workspace may run at a time, compute is paused after each session, and
temporary resources are deleted after evidence capture.

Secrets, tokens, connection strings, local credential caches, personal names,
and cloud identifiers must never be committed or printed. Portal screenshots
must be cropped or redacted before publication.

## Next execution increment

The local package builder now copies all 26 governed Parquet tables without
re-encoding them and publishes deterministic table and artifact hashes, Arrow
schemas, primary keys, date roles, access classifications, row/key counts, and
financial references. The package also includes a PySpark load-and-validation
notebook and a one-activity pipeline template. Full package data remains under
`data/generated/fabric_deployment` and outside Git; only the manifest and
machine-readable preparation evidence are publishable.

After the package increment is merged, activate the approved trial, create a
schema-enabled Lakehouse, upload the package contents, import the notebook,
configure the pipeline, reconcile the cloud tables, capture redacted evidence,
and tear down or pause all resources before closing M09.
