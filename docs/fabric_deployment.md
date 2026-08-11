# Microsoft Fabric and Azure Deployment Contract

## Purpose

M09 demonstrates that the locally governed synthetic analytics can be loaded,
queried, refreshed, and reconciled in Microsoft Fabric without changing their
business definitions. The portable package was executed on a Fabric Trial
capacity without provisioning a paid Azure resource.

## Verified readiness

Readiness was first checked interactively on 2026-08-09. Execution completed on
2026-08-10 using a Power BI Individual Trial and Fabric Trial capacity in North
Central US. An Azure for Students subscription remained available, but no paid
Azure resource was created for M09.

The evidence intentionally records only categorical status. Email addresses,
subscription and tenant identifiers, billing identifiers, tokens, and unredacted
screenshots are prohibited from Git and execution logs.

## Executed cloud architecture

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

The `hcpi-portfolio-m09` workspace contains the schema-enabled
`lh_hcpi_curated` Lakehouse, `nb_hcpi_load_validate` notebook, and
`pl_hcpi_curated_refresh` pipeline. The notebook materialized 26 Delta tables:
23 ordinary analytical tables and three restricted evaluation tables. It
published 33 reconciliation results, all of which passed. The pipeline then
executed the same notebook successfully.

The initial interactive notebook attempt exposed a Fabric-specific path issue:
absolute `/lakehouse/default/Files/...` paths were not accepted for the uploaded
Parquet files. The portable notebook now uses the Fabric-relative `Files` root,
which succeeded without changing any input data or governed calculation.

Cloud success is supported by machine-readable sanitized evidence. Private run
identifiers and full screenshots are retained outside Git; the public evidence
records their existence without publishing account or environment identifiers.

## Cost and security controls

The Fabric Trial was used after the contract was merged and the region was
confirmed. Any paid Azure provisioning still requires separate explicit
approval plus a budget and 50%, 80%, and 100% alerts. No paid resource was
created and the observed paid-resource cost is $0. The workspace is retained
temporarily so M10 can build and validate its Power BI semantic model and report;
teardown is due immediately after the final portfolio evidence is captured.

Secrets, tokens, connection strings, local credential caches, personal names,
and cloud identifiers must never be committed or printed. Portal screenshots
must be cropped or redacted before publication.

## Execution result and next step

The local package builder now copies all 26 governed Parquet tables without
re-encoding them and publishes deterministic table and artifact hashes, Arrow
schemas, primary keys, date roles, access classifications, row/key counts, and
financial references. The package also includes a PySpark load-and-validation
notebook and a one-activity pipeline template. Full package data remains under
`data/generated/fabric_deployment` and outside Git; only the manifest and
machine-readable preparation evidence are publishable.

The package, Lakehouse, notebook, and pipeline have now been executed and
reconciled successfully. M10 can consume the governed Lakehouse SQL analytics
endpoint to build the six-page Power BI report. The trial workspace must be
removed or allowed to expire after M10 evidence is safely captured.
