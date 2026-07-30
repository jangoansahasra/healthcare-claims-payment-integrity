# CMS Inpatient Provider-Service Silver Model

## Purpose

The inpatient Silver model creates a typed, longitudinal benchmark from the
CMS Medicare Inpatient Hospitals by Provider and Service public-use files. It
supports hospital and MS-DRG utilization, charge, and payment comparisons and
calibration of synthetic inpatient claims.

The data represents Original Medicare fee-for-service Part A activity at IPPS
hospitals. It is not claim-line or all-payer data.

## Grain and typing

The business key is:

- `hospital_ccn`
- `ms_drg_code`
- `reporting_year`

All 936,131 Bronze rows for 2019–2024 are preserved. CCN and DRG remain
`VARCHAR`, reporting year is `INTEGER`, total discharges are `BIGINT`, and the
three financial measures are `DECIMAL(38,6)`.

| Silver measure | CMS source field |
|---|---|
| `total_discharges` | `Tot_Dschrgs` |
| `average_submitted_covered_charge` | `Avg_Submtd_Cvrd_Chrg` |
| `average_total_payment` | `Avg_Tot_Pymt_Amt` |
| `average_medicare_payment` | `Avg_Mdcr_Pymt_Amt` |

## Payment semantics

CMS defines average covered charge as the hospital charge for Medicare-covered
services in the DRG. Average total payment includes Medicare payment,
beneficiary cost sharing, and third-party coordination-of-benefits amounts.
Average Medicare payment is the Medicare share and excludes those additional
amounts.

The model therefore enforces:

- nonnegative financial values;
- average Medicare payment not exceeding average total payment.

It does not enforce total payment below covered charge. The 1,915 observed rows
where total payment exceeds covered charge are retained with
`total_payment_above_covered_charge = true`.

## Historical dimensions and RUCA

Hospital names, addresses, locations, and RUCA values remain as reported in
each year. DRG descriptions are also year-specific because 11 codes have
observed description changes.

There are 681 rows with missing RUCA code and description. They receive an
`Unknown` analytical bucket and explicit source-missing indicators.

CMS also reports the literal description `Unknown` for RUCA code `99` in 3,834
rows. Consequently, 4,515 rows have an `Unknown` description, but only 681 are
source-missing. Downstream logic must use the Boolean missing indicator.

## Discharge-volume bands

Pooled 2019–2024 quartiles define the benchmark bands:

| Band | Discharges | Rows |
|---|---:|---:|
| Low | 11–13 | 199,913 |
| Medium | 14–20 | 265,422 |
| High | 21–35 | 234,063 |
| Very high | 36 or more | 236,733 |

The bands support cohort construction and do not represent anomaly or fraud
classifications.

## Governance

Real hospitals may be used for observed benchmarking, longitudinal analysis,
and synthetic calibration. Benchmark outliers must not be labeled as fraud or
incorrect payment, and injected anomalies remain confined to the separate
synthetic insurer dataset.

Public reporting excludes hospital name, street address, and ZIP code.
Minimum public peer groups require at least 11 hospitals.

## Outputs and validation

Generated local outputs:

- `data/interim/silver/cms_inpatient_provider_service.parquet`
- `data/metadata/quality/cms_inpatient_provider_service_silver.json`

The Parquet output remains excluded from Git. The contract, code, tests,
documentation, and quality report are versioned.

There are zero business-key, identifier, parsing, fractional-discharge,
publication-threshold, negative-value, or Medicare-payment relationship
violations. All 21 governed quality checks pass.
