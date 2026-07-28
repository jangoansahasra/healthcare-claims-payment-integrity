# CMS Physician Provider Summary Bronze Dataset

## Purpose

This source provides real, national provider-level Medicare fee-for-service
utilization, submitted-charge, allowed-charge, payment, beneficiary-mix, and
risk information for longitudinal claims-cost analysis.

It is aggregated provider-level public-use data, not individual claim-line
data.

## Source

- Publisher: Centers for Medicare & Medicaid Services
- Dataset: Medicare Physician and Other Practitioners by Provider
- Reporting years: 2019–2024
- Grain: one row per rendering provider NPI and reporting year
- Annual source columns: 81
- Schema groups: 1
- Direct beneficiary identifiers: none

## Acquisition

| Year | Raw CSV size | Bronze rows | Bronze Parquet size |
|---:|---:|---:|---:|
| 2019 | 438.1 MiB | 1,155,870 | 125.7 MiB |
| 2020 | 436.8 MiB | 1,161,542 | 124.7 MiB |
| 2021 | 451.5 MiB | 1,198,754 | 129.2 MiB |
| 2022 | 462.2 MiB | 1,230,293 | 131.7 MiB |
| 2023 | 472.4 MiB | 1,259,343 | 134.3 MiB |
| 2024 | 485.2 MiB | 1,296,739 | 139.2 MiB |
| Total | 2.7 GiB | 7,302,541 | 835 MiB |

Every raw file has a SHA-256 acquisition receipt. Raw CSV and generated
Parquet files are excluded from Git.

## Bronze design

All 81 CMS source columns are preserved as strings. Four lineage columns are
added:

- `_source_id`
- `_reporting_year`
- `_source_file`
- `_acquired_at_utc`

String preservation prevents loss of:

- leading zeroes;
- provider identifiers;
- CMS suppression tokens;
- not-applicable values;
- source-specific formatting.

Typing and special-value treatment will occur in the physician silver model.

## Validation

For every reporting year:

- raw CSV row count equals bronze Parquet row count;
- bronze row count equals the committed technical profile;
- rendering NPI is non-null;
- rendering NPI contains exactly 10 digits;
- rendering NPI remains `VARCHAR`;
- rendering NPI is unique within the year.

The six annual headers are identical and share one governed schema signature.

## Metadata

Annual profiles:

`data/metadata/profiles/cms_physician_provider_summary_<year>.json`

Family inventory:

`data/metadata/profiles/cms_physician_provider_summary_family.json`

The family inventory records:

- annual row counts;
- source-column counts;
- Parquet paths, sizes, and checksums;
- cross-year schema signatures;
- schema-consistency status.

## Limitations

- Represents Original Medicare fee-for-service activity.
- Does not represent each provider's complete practice.
- Provider-level aggregation cannot reproduce individual claim adjudication.
- Low-volume beneficiary information may be suppressed.
- NPI uniqueness is validated within each reporting year, not across years.
- Provider specialty or location changes must be handled historically.
