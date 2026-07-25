# Governed Source Manifest

The machine-readable source registry is maintained in
`config/source_manifest.yml`.

## Current-data standard

Core observed analysis uses the latest available official CMS public-use
releases. As of July 2026:

- Physician/provider/service data is available through 2024.
- Inpatient provider/service data is available through 2024.
- Part D provider/drug data is available through 2024.
- Outpatient provider/service data is available through 2023.
- Fiscal year 2026 ICD-10-CM references are available.
- 2026 HCPCS Level II quarterly references are available.

A source lag is reported explicitly and is not hidden by shifting observed
dates.

## Source roles

### Observed

Observed sources contain real, aggregated healthcare utilization and payment
activity derived from CMS administrative claims.

### Reference

Reference sources validate and categorize diagnosis and procedure codes.

### Simulated

Simulated claim headers, lines, transactions, membership, audits, and policy
assignments will be generated separately. Simulated fields will never be
presented as observed CMS records.

## Version resolution

CMS download URLs and version identifiers may change between annual releases.
The ingestion process will:

1. Query the official CMS catalog.
2. Resolve the requested reporting year.
3. Record the dataset type and version identifiers.
4. Record the resolved download URL.
5. Download to an ignored raw-data directory.
6. Calculate a SHA-256 checksum.
7. Save acquisition metadata.
8. Validate the source schema.
9. Convert the validated source to Parquet.

## Publication controls

The repository prohibits:

- Identifiable beneficiary data
- Restricted CMS research files
- Credentials and access tokens
- Proprietary CPT descriptions
- Complete raw or processed healthcare datasets

Only small, synthetic demonstration extracts may be committed.

## Legacy BSA decision

Basic Stand Alone Medicare Claims Public Use Files are excluded from the core
current-state analysis because their claim-line periods are too old for current
cost conclusions. They may be used only in an explicitly labeled legacy
ingestion appendix.