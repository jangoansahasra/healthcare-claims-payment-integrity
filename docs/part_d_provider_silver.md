# CMS Part D Prescriber Silver Model

## Purpose

The Part D prescriber silver model creates a typed, longitudinal pharmacy
benchmark from the official CMS Medicare Part D Prescribers by Provider
public-use files for 2019–2024.

It supports prescriber cost and utilization trends, pharmacy peer benchmarks,
and calibration of synthetic insurer claims. It is not claim-level data and
does not identify beneficiary transactions or insurer-only liability.

## Grain and coverage

The grain is one prescriber NPI per reporting year. The business key is
`prescriber_npi` plus `reporting_year`.

| Property | Value |
|---|---:|
| Reporting years | 2019–2024 |
| Prescriber-year rows | 7,913,081 |
| CMS source columns | 84 |
| Typed measures | 56 |
| Integer measures | 37 |
| Decimal measures | 19 |

NPI remains `VARCHAR`. Reporting year is `INTEGER`, governed counts are
`BIGINT`, and cost, rate, standardized-fill, age, and risk measures are
`DECIMAL(38,6)`. Populated values that cannot satisfy their governed type cause
the build to fail.

## Missing values

Source nulls are preserved and are never imputed to zero. Missing prescriber
type and RUCA values receive an `Unknown` analytical bucket plus a Boolean
source-missing indicator:

| Dimension | Missing rows |
|---|---:|
| Prescriber type | 27 |
| RUCA code | 8,977 |

No suppression reason is inferred for an unflagged null.

## Suppression lineage

CMS uses `*` for primary suppression and `#` for counter-suppression. The model
keeps affected measures null, retains the original indicator, assigns a
semantic status, and creates one lineage row per prescriber-year and suppressed
measure group.

| Status | Rows |
|---|---:|
| Primary suppressed | 16,923,033 |
| Counter-suppressed | 9,825,503 |
| Total | 26,748,536 |

The source indicators and lineage totals reconcile exactly. All 11 governed
suppression groups have valid token domains and consistent detail nulls.

## Prescriber-size bands

Size is based on total claims using pooled 2019–2024 empirical quartiles:

| Band | Total claims | Rows |
|---|---:|---:|
| Small | 11–55 | 1,974,146 |
| Medium | 56–200 | 1,978,707 |
| Large | 201–938 | 1,981,088 |
| Very large | 939 or more | 1,979,140 |

These bands support later cohort construction; they are not anomaly or fraud
classifications.

## Governance

The real CMS records are an observed benchmark. They may be used for pharmacy
cost and utilization comparisons, longitudinal analysis, and synthetic-data
calibration. They must not be used to reconstruct suppressed values, label a
real prescriber as fraudulent, or represent total drug cost as insurer-only
payment.

Country is required in peer definitions. State and RUCA comparisons are
domestic-only, while foreign rows are retained for country-specific analysis.
Minimum public peer groups require at least 11 prescribers.

## Outputs and validation

Generated local outputs:

- `data/interim/silver/cms_part_d_provider_summary.parquet`
- `data/interim/silver/cms_part_d_provider_suppressions.parquet`
- `data/metadata/quality/cms_part_d_provider_summary_silver.json`

The Parquet outputs remain excluded from Git. The contract, code, tests,
documentation, and quality report are versioned.

All 7,913,081 Bronze rows are preserved. There are no duplicate or null
business keys, invalid NPIs, unparseable numeric values, fractional integer
values, numeric range violations, invalid suppression tokens, or
suppression-detail violations. All 24 governed quality checks pass.
