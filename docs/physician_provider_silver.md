# CMS Physician Provider Silver Model

## Purpose

The physician provider silver model creates a typed, longitudinal benchmark
dataset from the official CMS Medicare Physician and Other Practitioners by
Provider public-use files.

The model supports:

- provider-level utilization and payment trends;
- specialty, geography, entity-type, and provider-size comparisons;
- beneficiary-mix and risk benchmarking;
- calibration of synthetic insurer claims;
- governed input for later cost-intelligence models.

This dataset is an observed benchmark. It is not a claim-line dataset and does
not contain insurer payment, reversal, adjustment, denial, or recovery events.

## Source coverage

| Property | Value |
|---|---|
| Publisher | Centers for Medicare & Medicaid Services |
| Reporting years | 2019–2024 |
| Source grain | One rendering provider NPI per reporting year |
| Source rows | 7,302,541 |
| Source columns | 81 |
| Silver measures | 62 |
| Percentage measures | 25 |
| Contains beneficiary identifiers | No |
| Contains public provider identifiers | Yes |

The official CMS data dictionary remains the authority for source-field
meaning and disclosure conventions.

## Silver grain and business key

The silver grain is:

> One rendering provider NPI per reporting year.

The business key is:

- `provider_npi`
- `reporting_year`

The source contains zero duplicate or null business keys and zero invalid
ten-digit NPIs.

Provider attributes are preserved as reported in each year. The model does not
overwrite historical specialty, address, geography, credentials, entity type,
or Medicare participation values with the latest observation.

## Data typing

The transformation:

- preserves NPI as `VARCHAR`;
- casts reporting year to `INTEGER`;
- casts governed count measures to `BIGINT`;
- casts remaining analytical measures to `DECIMAL(38,6)`;
- rejects populated values that cannot be converted;
- preserves analytical nulls rather than imputing zero;
- retains acquisition lineage.

The transformation found no unparseable numeric values, fractional violations
in governed integer measures, negative count values, negative service values,
or negative financial values.

## CMS suppression handling

CMS uses two provider-summary suppression indicators:

- `*` means the associated beneficiary count is fewer than 11;
- `#` means the value is counter-suppressed to prevent reconstruction of
  another suppressed value.

The silver model:

- keeps affected numeric values null;
- never converts suppressed values to zero;
- never reconstructs suppressed values;
- translates source tokens into machine-readable statuses;
- creates one long-form lineage row per provider-year and suppressed measure
  group;
- validates that suppression indicators agree with the corresponding detail
  fields.

Validated lineage totals:

| Status | Rows |
|---|---:|
| Primary suppressed, fewer than 11 | 835,298 |
| Counter-suppressed | 833,424 |
| Total suppression lineage | 1,668,722 |

The source-indicator and lineage totals reconcile exactly.

## Chronic-condition top-coding

CMS chronic-condition percentage values are capped at 75. A reported value of
75 means 75 percent or greater, not exactly 75 percent.

The model therefore:

- preserves the numeric value;
- creates one Boolean top-coded indicator per percentage metric;
- creates a row-level `top_coded_metric_count`;
- prevents downstream documentation from treating 75 as an exact percentage.

Results:

- 25 governed percentage metrics;
- 9,602,567 top-coded cells;
- 5,399,402 provider-year rows with at least one top-coded metric;
- maximum of 12 top-coded metrics on one provider-year row.

Wide indicators and row-level top-coded counts reconcile exactly.

## Provider-size classification

Provider size is based on `tot_benes`:

| Band | Beneficiaries | Provider-year rows |
|---|---:|---:|
| Small | 11–49 | 1,633,441 |
| Medium | 50–199 | 2,795,938 |
| Large | 200–999 | 2,523,707 |
| Very large | 1,000 or more | 349,455 |

These bands support later peer-group construction. They do not themselves
constitute performance or anomaly classifications.

## Geographic safeguards

The source contains 38 country codes and 460 non-US provider-year rows.

The model retains all provider rows and requires country-aware peer
definitions. Future state and RUCA comparisons will be limited to domestic
records. Foreign providers will be grouped by country rather than mixed into
US state or rurality cohorts.

The silver layer validates that these safeguards are configured. Actual
minimum-size peer-group eligibility will be calculated and tested in the
benchmark gold layer.

## Privacy and interpretation

The public portfolio dashboard will exclude direct provider-detail fields such
as street address, personal name, credentials, and ZIP code.

Real CMS provider records may be used for benchmarks and aggregate trends, but
they must not be used to:

- attribute injected anomalies to real providers;
- label a benchmark outlier as fraud or incorrect payment;
- reconstruct suppressed beneficiary values;
- represent provider summaries as claim-line transactions;
- present synthetic audit rules as production medical policy.

Payment-integrity anomalies will be injected only into the separately generated
synthetic insurer dataset.

## Outputs

Generated local outputs:

- `data/interim/silver/cms_physician_provider_summary.parquet`
- `data/interim/silver/cms_physician_provider_suppressions.parquet`
- `data/metadata/quality/cms_physician_provider_summary_silver.json`

The generated Parquet files remain excluded from Git. The contract,
transformation code, tests, documentation, and quality report are versioned.

## Validation results

- Bronze rows: 7,302,541
- Silver rows: 7,302,541
- Typed measures: 62
- Reporting years retained: 2019–2024
- Duplicate business keys: 0
- Null business keys: 0
- Invalid NPIs: 0
- Null country codes: 0
- Invalid suppression tokens: 0
- Suppression-detail violations: 0
- Numeric-range violations: 0
- Quality checks: 23 of 23 passed
- Project tests after implementation: 96 passed