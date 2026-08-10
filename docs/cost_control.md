# Cloud Cost-Control Plan

## Current constraint

The available Azure credit is limited, so the full analytical workload is built
and tested locally before cloud deployment.

As verified on 2026-08-09, a university Fabric Free account with an available
trial offer and an active Azure for Students subscription are available. The
Fabric trial is not active and no M09 cloud resource has been provisioned.

## Rules

1. Do not leave paid compute running between work sessions.
2. Prefer the Fabric trial for Lakehouse, Warehouse, pipeline, and Power BI
   demonstrations.
3. Store only the final curated portfolio-sized dataset in cloud storage.
4. Configure Azure budgets and alerts before provisioning paid resources.
5. Use locally generated Parquet files instead of repeated cloud ingestion.
6. Use GitHub Actions on standard runners and keep artifacts small.
7. Delete temporary Azure resources after evidence and screenshots are saved.
8. Never bypass licensing, account, quota, or billing controls.

## Legitimate substitutes

| Paid or limited component | Cost-safe development substitute |
|---|---|
| ADLS Gen2 | Local partitioned Parquet |
| Synapse serverless SQL | DuckDB SQL over Parquet |
| Fabric Warehouse | DuckDB schemas/views |
| Fabric pipeline | Python CLI plus GitHub Actions |
| Key Vault | Local `.env` excluded from Git |
| Power BI sharing | Local PBIX or Fabric trial workspace |
| Azure Windows VM | Existing Windows device or time-limited VM only for PBIX |

## Before Azure provisioning

- Confirm the subscription and remaining credit.
- Create a project-specific resource group.
- Add a small budget and alerts.
- Record every resource, SKU, region, and deletion procedure.
- Estimate the maximum session cost.
- Require explicit approval before activating paid capacity.
- Record teardown completion and final observed cost after the demo.
