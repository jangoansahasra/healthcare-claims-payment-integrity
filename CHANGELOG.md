# Changelog

All material changes to the Healthcare Claims Payment Integrity & Cost
Intelligence Platform are documented here.

The project follows milestone-based development. Each completed feature must
include validation evidence and corresponding documentation.

## Unreleased

### Added

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
