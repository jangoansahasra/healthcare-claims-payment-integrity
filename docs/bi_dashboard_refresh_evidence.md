# BI dashboard refresh evidence

This file records sanitized refresh evidence for the two M10 presentation
tools, satisfying `config/bi_semantic_contract.yml`'s `evidence.refresh_fields`
contract. No account, tenant, subscription, workspace, or run identifiers
are recorded here or in any accompanying screenshot.

## Looker Studio (LS01 - Executive overview)
- environment: web browser, Looker Studio
- tool: Looker Studio
- refreshed_at_utc: 2026-08-24T23:26:04Z
- source_artifact_hashes: full per-extract SHA-256 hashes are published in
  `data/metadata/quality/bi_dashboard_extracts.json`; the `executive_kpi`
  extract behind this page is
  `1eb3535da170f68fcd83fabc5fdb73760bd1956abf4b622ae6be7716aa707c1d`.
- metric_result_hash:
  `83b48c6b33ad2d3354a9b3dd444746f708d24bd868889c0744b8089af75c1e64`
  (SHA-256 of `BI001=<value>|BI002=<value>|BI003=<value>|BI004=<value>`
  read from the governed `executive_kpi` extract)

## Power BI (My workspace)
- environment: web browser, Power BI Service, My workspace
- tool: Power BI
- refreshed_at_utc: 2026-08-24T23:23:16Z
- connection: Excel workbook (`executive_kpi` extract) imported through
  OneDrive, per DL-012, because the Fabric Trial capacity had expired
- source_artifact_hashes: `executive_kpi` extract,
  `1eb3535da170f68fcd83fabc5fdb73760bd1956abf4b622ae6be7716aa707c1d`
- metric_result_hash:
  `83b48c6b33ad2d3354a9b3dd444746f708d24bd868889c0744b8089af75c1e64`
  (identical to Looker Studio, confirming both tools reproduce the same
  governed values)

## Validation
Both tools reproduce total allowed amount, total paid amount, allowed
PMPM, and paid PMPM from the same governed extract with zero count
difference and financial differences within $0.01. Screenshots captured
alongside this evidence expose no account, tenant, subscription,
workspace, or run identifiers.
