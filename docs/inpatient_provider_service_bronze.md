# CMS Inpatient Provider-Service Bronze Dataset

## Purpose

This dataset provides observed Original Medicare inpatient utilization and
payment benchmarks at hospital CCN, MS-DRG, and reporting-year grain. It
supports discharge, hospital, DRG-mix, charge, and payment analysis and later
calibration of synthetic insurer claims.

It is aggregated public-use data, not claim-line or beneficiary-level data.

## Acquisition and coverage

| Year | Raw size | Rows | Bronze size |
|---:|---:|---:|---:|
| 2019 | 46.41 MiB | 187,719 | 3.61 MiB |
| 2020 | 39.23 MiB | 158,375 | 3.10 MiB |
| 2021 | 37.67 MiB | 151,989 | 2.99 MiB |
| 2022 | 36.13 MiB | 145,742 | 2.87 MiB |
| 2023 | 36.35 MiB | 146,427 | 2.87 MiB |
| 2024 | 36.22 MiB | 145,879 | 2.86 MiB |
| Total | 232 MiB | 936,131 | 18 MiB |

All annual files have valid SHA-256 receipts. Raw CSV and generated Parquet
files remain excluded from Git.

## Encoding governance

The 2019–2023 files contain Windows-1252 punctuation, including byte `0x96`
for an en dash. The 2024 file is UTF-8.

The converter applies an explicit encoding by year, decodes strictly, streams
non-UTF-8 text into a temporary UTF-8 input, preserves the raw file, removes
temporary inputs, and atomically replaces the final Parquet output. It never
skips malformed rows or uses lossy replacement characters.

## Bronze design and validation

All 15 CMS columns remain strings and four acquisition-lineage columns are
added. The annual schemas are identical and form one schema group.

The business key is `Rndrng_Prvdr_CCN`, `DRG_Cd`, and `_reporting_year`.
Validation found zero duplicate or null keys, zero invalid six-character CCNs,
zero invalid three-digit DRG codes, and exact annual row-count reconciliation.
The family contains 3,209 hospitals and 631 DRG codes.

The four analytical numeric candidates are complete and parseable:

- `Tot_Dschrgs`
- `Avg_Submtd_Cvrd_Chrg`
- `Avg_Tot_Pymt_Amt`
- `Avg_Mdcr_Pymt_Amt`

Discharges are integral and at least 11 because provider-DRG combinations with
10 or fewer discharges are excluded from publication.

## Interpretation limitations

The data represents Original Medicare fee-for-service activity, not all-payer
hospital activity. Average values cannot reproduce claim adjudication.

Medicare payment never exceeds total payment. Average total payment exceeds
average submitted covered charge in 1,915 observed rows; those values are
retained and are not rejected without an authoritative semantic rule.

`Rndrng_Prvdr_St` is the provider street-address field. State-level analysis
must use `Rndrng_Prvdr_State_FIPS`.

## Metadata

Annual profiles use
`data/metadata/profiles/cms_inpatient_provider_service_<year>.json`.
The family inventory is
`data/metadata/profiles/cms_inpatient_provider_service_family.json`.
