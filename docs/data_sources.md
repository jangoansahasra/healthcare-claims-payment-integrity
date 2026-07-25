# Data Sources

## Data strategy

The project combines official public-use healthcare data with clearly labeled
synthetic insurer operations and controlled anomaly injection.

Official data provides genuine healthcare utilization and payment patterns.
Synthetic data fills fields that are proprietary, protected, or unavailable
in public claims data. Controlled anomalies provide known ground truth for
objective rule evaluation.

## Official sources

| Source | Publisher | Data type | Planned use | Status |
|---|---|---|---|---|
| Basic Stand Alone Medicare Claims PUF | CMS | De-identified claim-specific public-use data | Claims foundation and SAS ingestion | Planned |
| Medicare Physician & Other Practitioners | CMS | Aggregated provider and service utilization and payment data | Provider benchmarks and cost analysis | Planned |
| ICD-10-CM files | CDC/NCHS | Diagnosis reference | Code validation and diagnosis categories | Planned |
| HCPCS Level II files | CMS | Procedure reference | Procedure validation and categories | Planned |
| Place of Service code set | CMS | Service-location reference | Claims classification | Planned |
| NPPES public data | CMS | Provider reference | Provider attributes where appropriate | Planned |

## Synthetic operational tables

The following data is not normally available in unrestricted public claims
files and will be generated:

- Member and plan dimensions
- Membership-month eligibility
- Provider contracts
- Claim submission and adjudication events
- Payments, reversals, and adjustments
- Claim-review outcomes
- Denial outcomes
- Policy treatment assignments
- Audit outcomes and recoveries

## Controlled anomaly types

- Exact duplicate claim lines
- Near-duplicate claim lines
- Payments remaining after reversal
- Paid amounts above allowed amounts
- Impossible service and payment dates
- Header and line total mismatches
- Repeated procedures above configured limits
- Invalid or missing codes
- Provider billing outliers
- Sudden provider utilization increases

## Source manifest requirements

Every downloaded file must be registered with:

- Dataset name
- Publisher
- Source page
- Direct download URL
- Retrieval date
- Source release or reporting period
- Local filename
- File size
- SHA-256 checksum
- Usage terms
- Documentation URL
- Ingestion status

## Publication rules

- Never commit restricted beneficiary-level data.
- Never commit credentials, access tokens, or cloud secrets.
- Do not redistribute proprietary CPT descriptions.
- Keep complete downloaded and generated datasets outside Git.
- Publish only small, fully synthetic sample extracts.
- Distinguish observed fields from simulated fields.
- Preserve the unmodified source file separately from transformed data.
- Document all filtering, recoding, and date-shifting operations.