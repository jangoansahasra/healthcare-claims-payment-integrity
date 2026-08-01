# CMS Physician Provider-Service Bronze Family

## Purpose

This Bronze family preserves the CMS Medicare Physician & Other Practitioners
by Provider and Service public-use data for 2019–2024. It supports observed
provider-HCPCS-place-of-service utilization, charge, allowed-amount, payment,
and standardized-payment benchmarks.

The source contains aggregated Original Medicare fee-for-service activity. It
is not claim-line data, does not represent a provider's complete practice, and
does not contain known improper-payment labels.

## Coverage

| Year | Rows | Parquet size |
|---:|---:|---:|
| 2019 | 10,140,228 | 319.72 MiB |
| 2020 | 9,449,361 | 307.57 MiB |
| 2021 | 9,886,177 | 312.32 MiB |
| 2022 | 9,755,427 | 320.07 MiB |
| 2023 | 9,660,647 | 312.21 MiB |
| 2024 | 9,781,673 | 323.97 MiB |
| **Total** | **58,673,513** | **1.90 GiB** |

All six files use one consistent 28-column CMS schema. Strict UTF-8 decoding
completed without ignored or replaced bytes. Four standard acquisition-lineage
columns are added to Parquet.

## Grain and identifiers

The observed business key is rendering NPI, HCPCS code, place-of-service
category, and reporting year. Identifiers remain strings to preserve their
source representation.

- duplicate business keys: 0
- null business keys: 0
- invalid ten-digit NPIs: 0
- invalid five-character HCPCS codes: 0
- place-of-service domain: `F` facility and `O` office
- entity domain: `I` individual and `O` organization
- drug-indicator domain: `N` and `Y`

## Numeric observations

All seven numeric candidates are present on every row and parse without
nonnumeric tokens:

- total beneficiaries
- total services
- total beneficiary-day services
- average submitted charge
- average Medicare allowed amount
- average Medicare payment
- average Medicare standardized payment

Beneficiary counts and beneficiary-day service counts are integral. Total
services contains 55,901 fractional values because HCPCS-specific service units
can be non-integral. Silver must therefore preserve total services as a decimal
measure rather than forcing it to an integer.

The minimum beneficiary count is 11, consistent with publication suppression
for low-volume provider-service combinations. Absence below the publication
threshold is not zero activity and suppressed records must not be reconstructed.

## Payment observations

Medicare payment never exceeds Medicare allowed amount. The family also
contains observed relationships that must be interpreted rather than rejected:

- allowed amount above submitted charge: 101,936 rows
- Medicare payment above submitted charge: 10,104 rows
- standardized payment above allowed amount: 3,258,449 rows

Submitted charge is not an expected-payment ceiling. Standardized payment is
an analytically adjusted amount intended to remove geographic payment-rate
differences, so it is not constrained to be below the unstandardized allowed
amount.

## Missing dimensions

Provider type, HCPCS description, and country are complete. The source has
6,134 rows with missing state FIPS and 41,175 rows with missing RUCA code.
These values remain missing in Bronze and require explicit indicators and
country-safe peer grouping in Silver.

## Reconciliation and storage

For every year, raw CSV line count minus one header row equals both Parquet and
profile row counts. All acquisition receipts continue to validate after
conversion. Raw CSV files and generated Parquet files remain excluded from
Git; only configuration, profiles, tests, and documentation are versioned.

## Analytical guardrails

- Benchmark deviation is not evidence of fraud or improper payment.
- Service counts must be interpreted according to the HCPCS unit definition.
- Facility-setting professional payment does not represent the facility's payment.
- Real providers must remain separate from synthetic anomaly labels.
- Missing or unpublished data must not be imputed as zero.
