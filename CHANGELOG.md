# Changelog

All material changes to the Healthcare Claims Payment Integrity & Cost
Intelligence Platform are documented here.

The project follows milestone-based development. Each completed feature must
include validation evidence and corresponding documentation.

## Unreleased

### Added

- Deterministic synthetic member, plan, provider, contract, eligibility, and
  policy-assignment generator
- Contract-derived Arrow schemas and atomic Zstandard Parquet output
- Machine-readable synthetic dimension quality report and content hashes
- Small synthetic-only demonstration samples for six operational tables
- Versioned synthetic insurer operational-data contract covering 14 tables
- Deterministic generation, identifier, lifecycle, and reconciliation controls
- Append-only adjudication, payment, and recovery ledger semantics
- Automated synthetic contract, key, privacy, and storage-policy tests
- Initial repository foundation
- Cost-safe local-to-Fabric architecture
- Payment-integrity rule configuration
- Reporting and claims-history decision log
- Cloud cost-control plan
- Public GitHub repository
- Python 3.12 project environment configuration
- Ruff and pytest project configuration
- Automated configuration validation tests
- GitHub Actions continuous-integration workflow
- Project-relative VS Code Python and test settings
- Governed current CMS source manifest
- Official CMS catalog discovery module
- Annual CMS distribution resolver for 2019–2024
- Persisted source-resolution metadata
- Remote source-size probing without full downloads
- Persisted remote-file inventory
- Automated source-governance, catalog, resolver, and probe tests
- Tiered acquisition policy for seven CMS source families
- Resumable streaming downloads with disk-capacity controls
- SHA-256 acquisition receipts for downloaded source files
- String-preserving bronze Parquet conversion with Zstandard compression
- Machine-readable Parquet technical profiles
- Automated acquisition, download, conversion, and profiling tests
- First validated CMS Geographic Variation bronze dataset covering 2014–2024
- Governed CMS Geographic Variation silver contract
- Typed 241-measure geographic silver transformation
- Stable identifiers for coded and aggregate geographies
- Separate suppression and not-applicable value lineage
- Automated silver range, grain, row-count, and domain validation
- Controlled end-to-end silver integration tests
- Machine-readable silver quality report
- Reusable multi-year CMS source-family bronze converter
- Validated CMS outpatient provider-service Bronze family for the published
  2019, 2021, and 2023 periods
- Strict period-specific Windows-1252 and UTF-8 outpatient decoding
- Outpatient annual profiles and cross-period schema inventory
- Governed CMS outpatient hospital-APC Silver contract and transformation
- Explicit provider-APC, beneficiary-count, and outlier suppression statuses
- Outpatient payment-relationship checks and machine-readable quality report
- Validated CMS physician provider-service Bronze family covering 2019–2024
- Technical profiles for 58.7 million provider-HCPCS-place-of-service rows
- Explicit preservation of fractional HCPCS service units and source geography missingness
- Governed physician provider-HCPCS-place-of-service Silver transformation
- Country-safe provider-service peer geography and beneficiary-volume bands
- Machine-readable quality report for 58.7 million typed service records
- Cross-year schema consistency and drift metadata
- Six-year CMS physician provider-summary bronze dataset
- Provider NPI grain and format reconciliation
- Automated source-family discovery and conversion tests
- Governed longitudinal CMS physician provider silver contract
- Typed 62-measure physician provider transformation
- Historical provider attributes preserved by reporting year
- Official primary and counter-suppression lineage
- Chronic-condition percentage top-coding indicators
- Country-safe provider benchmark configuration
- Provider-size benchmark classification
- Machine-readable physician silver quality report
- Automated physician contract, helper, and end-to-end transformation tests
- Governed schema-alias support for multi-year CMS bronze conversion
- Six-year CMS Part D prescriber provider-summary bronze dataset
- Canonical Part D prescriber NPI and provider-type-source fields
- Seven Part D bronze technical profiles and family inventory
- Automated schema-alias collision and Parquet-renaming tests
- Governed longitudinal CMS Part D prescriber silver contract
- Typed 56-measure Part D prescriber transformation
- Official primary and counter-suppression lineage for 11 measure groups
- Explicit preservation of unflagged source nulls and missing dimensions
- Country-safe prescriber benchmark and quartile size-band configuration
- Machine-readable Part D silver quality report
- Automated Part D contract, helper, and end-to-end transformation tests
- Governed per-year source encoding and strict streaming transcoding
- Six-year CMS inpatient provider-DRG Bronze dataset
- Seven inpatient Bronze technical profiles and family inventory
- Atomic Parquet conversion with temporary-file cleanup
- Automated encoding, raw-integrity, and transcoding tests
- Governed longitudinal CMS inpatient provider-DRG Silver contract
- Typed discharge, covered-charge, total-payment, and Medicare-payment measures
- Explicit RUCA missing lineage and year-specific hospital attributes
- Observed payment-above-charge indicator without false rejection
- Hospital-DRG discharge-volume benchmark bands
- Machine-readable inpatient Silver quality report
- Automated inpatient contract, helper, and end-to-end transformation tests
- Validated CMS Part D provider-drug Bronze family covering 2019–2024
- Technical profiles for 156.5 million prescriber-brand-generic records
- Strict year-specific UTF-8 and Windows-1252 source decoding
- Explicit preservation of beneficiary and age-group suppression lineage
