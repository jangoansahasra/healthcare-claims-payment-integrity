# Changelog

All material changes to the Healthcare Claims Payment Integrity & Cost
Intelligence Platform are documented here.

The project follows milestone-based development. Each completed feature must
include validation evidence and corresponding documentation.

## Unreleased

### Fixed

- Enabled CI push validation for `codex/**` branches so agent-authored pull
  requests receive a head-SHA check even when GitHub omits the PR event
- Prevented missing SAS reconciliation values from passing tolerance checks
  under SAS missing-value ordering semantics
- Preserved 64-character comparison scopes when combining domain metric tables,
  eliminating truncation warnings and unmatched reference rows
- Required and published a real execution identifier on every reconciliation
  result row to satisfy the governed result grain and primary key

### Added

- Versioned M09 Fabric deployment contract with verified categorical readiness,
  deterministic artifact naming, governed M04-M07 table mappings, reconciliation,
  security, cost, evidence, and teardown controls
- Trial-first cloud architecture preserving evaluation-ground-truth isolation,
  service/payment date roles, exact row and key counts, and one-cent financial
  tolerances without provisioning any cloud resource
- Portable six-input SAS package builder, 181 Python references, SHA-256
  manifests, seven ordered SAS programs, and governed log scanning
- Versioned M08 SAS reconciliation registry, portable exchange specification,
  execution evidence rules, tolerances, log policy, and non-SAS contract tests
- Deterministic M07 provider-month panel, weighted two-way fixed-effects
  estimates, event study, clustered inference, diagnostics, and sensitivities
- Typed synthetic samples and machine-readable policy-analysis quality evidence
- Versioned M07 provider-panel, difference-in-differences, event-study,
  parallel-trends, placebo, sensitivity, and statistical-output contracts
- Deterministic five-table M06 cost-intelligence generator with reconciled
  service cost, payment cash flow, concentration, decomposition, and warnings
- Synthetic samples, stable content hashes, deterministic Parquet bytes, and
  machine-readable M06 quality evidence
- Versioned M06 cost-intelligence contracts for PMPM, per-1,000 utilization,
  payment cash flow, concentration, cost decomposition, and early warnings
- Explicit eligible member-month denominators, service/payment date roles,
  ground-truth exclusion, small-cell suppression, and reconciliation controls
- Clean-runner CI fixture generation for ignored synthetic, anomalous, and
  trusted Parquet inputs used by M05 integration tests
- Linear-time anomaly lineage sequencing and preexisting-line validation for
  practical reproducible CI execution
- Deterministic PI001–PI010 rules engine with frozen explainable findings,
  sequenced evidence, isolated ground-truth matching, and evaluation metrics
- Five typed M05 Parquet outputs, synthetic samples, machine-readable quality
  evidence, and deterministic content/byte validation
- Versioned M05 rules-engine findings, evidence, matching, and evaluation
  contracts for all ten governed payment-integrity rules
- Explicit ground-truth leakage boundary, canonical label-scope matching,
  reproducible metric formulas, and portfolio performance thresholds
- Deterministic twelve-table trusted claims generator with typed Zstandard
  Parquet, stable surrogate keys, and synthetic demonstration samples
- End-to-end current-version, financial, eligibility, foreign-key, policy, and
  500-label anomaly-bridge reconciliation evidence
- Versioned M04 trusted-claims dimensional contract with deterministic
  surrogate keys, explicit claim-version scope, and reconciled fact measures
- Evaluation-only anomaly bridge, conformed date roles, and curated-output
  privacy and publication controls
- Deterministic PI009 procedure-frequency and PI010 diagnosis-procedure
  incompatibility anomaly injection
- Complete ten-rule M03 ground truth with governed clinical mappings,
  repetition ceilings, isolation checks, and reproducible Parquet output
- Deterministic PI007 provider-amount and PI008 provider-period utilization
  anomaly injection
- Specialty/service-system peer thresholds, historical utilization baselines,
  complete lifecycle insertion lineage, and exposure reconciliation
- Composable PI003 reversal-ledger and PI004 impossible-payment-date injection
- Append-only reversal linkage, temporal lineage, and unresolved-exposure checks
- Immutable M02 baseline cloning and 14-table hash-manifest generation
- Deterministic PI001, PI002, PI005, and PI006 record-level anomaly injection
- Field-level mutation lineage, exposure reconciliation, and isolation validation
- Versioned PI001–PI010 anomaly-injection scenario contracts
- Ground-truth, field-change lineage, and clean-baseline hash-manifest schemas
- Deterministic target-selection, overlap, exposure, privacy, and storage controls
- Deterministic clean claim-review and audit workflow
- Fully typed zero-row recovery ledger preserving the M02 clean-baseline boundary
- End-to-end quality validation and content hashes across all 14 operational tables
- Deterministic clean synthetic claim lifecycle with 75,000 versioned headers
- Contract-conforming claim lines, adjudication events, denials, and payments
- Eligibility, contract, lifecycle, version, and financial reconciliation checks
- Machine-readable claim-lifecycle quality report and synthetic-only samples
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
