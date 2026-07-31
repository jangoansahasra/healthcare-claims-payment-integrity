# CMS Outpatient Hospital-APC Silver Model

## Purpose

This model provides typed, governed benchmarks for Original Medicare
fee-for-service Part B services furnished by OPPS hospitals and summarized by
hospital CCN, comprehensive APC, and published reporting period.

It contains observed aggregated activity—not claim lines or improper-payment
labels. Real hospitals must not receive synthetic anomaly or fraud labels.

## Coverage and grain

The model retains all 350,393 Bronze rows from the published 2019, 2021, and
2023 periods. It does not interpolate 2020, 2022, or 2024 or present the data
as a complete annual panel. The business key is:

- `hospital_ccn`
- `comprehensive_apc_code`
- `reporting_period`

CCNs and APC codes remain strings. Hospital and APC descriptions remain
period-specific rather than being overwritten with current values.

## Typed measures

Three count measures use `BIGINT`:

- beneficiary count
- comprehensive APC services
- outlier services

Four monetary measures use `DECIMAL(38,6)`:

- average submitted charge
- average Medicare allowed amount
- average Medicare payment
- average Medicare outlier amount

Null source values remain null; the model never imputes zero.

## Suppression semantics

CMS applies separate publication thresholds. The model creates explicit
`published` or `suppressed` statuses for each group:

| Status group | Governing CMS threshold | Suppressed rows |
|---|---|---:|
| Provider-APC summary | 10 or fewer comprehensive APC services | 157,739 |
| Beneficiary count | 10 or fewer beneficiaries | 161,089 |
| Outlier detail | 10 or fewer outlier services | 211,218 |

Suppressed values are not reconstructed. A suppressed value is not zero and
does not establish that no activity occurred.

## Payment semantics

The average allowed amount includes the regular Medicare payment plus
beneficiary cost sharing and qualifying third-party payments. The regular
Medicare payment must therefore not exceed the allowed amount; the production
data has zero violations.

Submitted charges are billed amounts, not contractual payment ceilings.
Accordingly, 85 allowed-above-charge and 49 Medicare-payment-above-charge rows
are retained and reported. Outlier payments are separate from regular
payments, so the 3,082 outlier-above-regular-payment rows are also retained.

## Derived fields

The model provides explicit suppression statuses, RUCA missing indicators,
service-volume bands, and observed payment-relationship indicators. Service
bands use pooled non-suppressed comprehensive APC service quartiles:

- low: 11–20
- medium: 21–38
- high: 39–88
- very high: 89 or more
- suppressed: unpublished service count

## Quality results

- Bronze rows: 350,393
- Silver rows: 350,393
- typed measures: 7
- duplicate or null business keys: 0
- invalid CCNs, APCs, state FIPS codes, or ZIP codes: 0
- fractional count values: 0
- negative count or financial values: 0
- Medicare-payment-above-allowed violations: 0
- missing RUCA code and description rows: 18 each
- all 26 quality checks passed

The generated Silver Parquet is excluded from Git. The contract, builder,
quality report, tests, and documentation are versioned.

## Reporting guardrails

- Compare only within published periods and sufficiently sized peer groups.
- Label results as observed benchmarks, not expected claim payments.
- Do not infer suppressed values or convert them to zero.
- Do not expose direct hospital details in public-facing benchmark views.
- Do not interpret benchmark deviation as fraud or improper payment.
