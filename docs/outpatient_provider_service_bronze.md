# CMS Outpatient Provider-Service Bronze Family

## Purpose

This Bronze family preserves the published CMS Medicare Outpatient Hospitals
by Provider and Service records for observed hospital, APC service,
utilization, charge, allowed-amount, payment, and outlier benchmarks.

The data is aggregated Original Medicare fee-for-service activity. It is not
claim-line data, does not represent all payers, and does not contain known
incorrect-payment labels.

## Published periods

CMS currently provides the configured 2019, 2021, and 2023 distributions. The
project retains those periods exactly and does not synthesize or interpolate
2020, 2022, or 2024 observations.

| Period | Rows | Source encoding | Parquet size |
|---:|---:|---|---:|
| 2019 | 115,507 | Windows-1252 | 1.89 MiB |
| 2021 | 118,087 | Windows-1252 | 1.82 MiB |
| 2023 | 116,799 | UTF-8 | 1.83 MiB |
| **Total** | **350,393** | — | **5.54 MiB** |

## Grain and identifiers

The observed business key is rendering-provider CCN, APC code, and reporting
period. CCNs and APC codes remain strings so leading zeroes and source
formatting are preserved. Across all periods:

- duplicate business keys: 0
- null business keys: 0
- invalid six-character CCNs: 0
- invalid four-digit APC codes: 0
- invalid two-digit state FIPS codes: 0
- invalid five-digit ZIP codes: 0

## Encoding controls

The 2019 and 2021 files are decoded strictly as Windows-1252; the 2023 file is
decoded as UTF-8. Conversion streams non-UTF-8 sources through temporary UTF-8
inputs without modifying the receipt-governed raw files. Decode errors are not
ignored and invalid bytes are not silently replaced.

All three periods have the same 18-column source schema. The Parquet files add
the standard source identifier, reporting period, source file, and acquisition
timestamp lineage fields.

## Numeric observations

The seven numeric candidates contain no nonnumeric tokens. Beneficiary,
comprehensive APC service, and outlier service counts have no fractional
values. Source nulls are preserved rather than imputed:

| Column | Non-null | Null |
|---|---:|---:|
| `Bene_Cnt` | 189,304 | 161,089 |
| `CAPC_Srvcs` | 192,654 | 157,739 |
| `Avg_Tot_Sbmtd_Chrgs` | 192,654 | 157,739 |
| `Avg_Mdcr_Alowd_Amt` | 192,654 | 157,739 |
| `Avg_Mdcr_Pymt_Amt` | 192,654 | 157,739 |
| `Outlier_Srvcs` | 139,175 | 211,218 |
| `Avg_Mdcr_Outlier_Amt` | 139,175 | 211,218 |

These nulls require semantic treatment in Silver; Bronze does not infer zero,
suppression, or non-applicability without an explicit source definition.

## Coverage and missing dimensions

The family contains 3,576 hospitals, 70 APC codes, 50 state FIPS values, and
19 non-null RUCA codes. Eighteen rows have both RUCA code and description
missing; the paired missingness is preserved explicitly. Organization names,
state FIPS values, and APC descriptions are complete.

## Reconciliation

CSV, Parquet, and profile row counts match for every period. All six source
files continue to validate against their acquisition receipts after
conversion. Raw CSV and generated Parquet files remain excluded from Git;
only reproducibility configuration, technical profiles, tests, and
documentation are versioned.

## Analytical limitations

- Available-period comparisons must not be presented as an annual time series.
- Aggregated provider-service records cannot reproduce a claim lifecycle.
- Published values may reflect CMS privacy and publication rules.
- Benchmark deviation is not evidence of fraud or improper payment.
- Synthetic anomaly labels must remain separate from real hospital records.
