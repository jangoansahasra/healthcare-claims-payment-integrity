# CMS Part D Provider-Drug Bronze Family

## Purpose

This Bronze family preserves the CMS Medicare Part D Prescribers by Provider
and Drug public-use data for 2019–2024. It supports observed prescriber-drug
utilization, beneficiary, days-supply, standardized-fill, and total-cost
benchmarks.

The source contains aggregated prescription drug events for beneficiaries
enrolled in Medicare Part D. It is not claim-level data, is not representative
of a prescriber's complete practice, and contains no known fraud or
improper-payment labels.

Official CMS resources:

- [Dataset](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/medicare-part-d-prescribers-by-provider-and-drug)
- [Methodology](https://data.cms.gov/resources/medicare-part-d-prescribers-methodology)

## Coverage

| Year | Rows | Parquet size |
|---:|---:|---:|
| 2019 | 25,401,870 | 465.54 MiB |
| 2020 | 25,209,729 | 465.35 MiB |
| 2021 | 25,231,862 | 467.61 MiB |
| 2022 | 25,869,521 | 481.86 MiB |
| 2023 | 26,794,878 | 503.21 MiB |
| 2024 | 28,023,892 | 527.09 MiB |
| **Total** | **156,531,752** | **2.84 GiB** |

All six releases use one consistent 22-column source schema. Four acquisition
lineage columns are added to Bronze Parquet.

## Grain and identifiers

The observed business key is prescriber NPI, brand name, generic name, and
reporting year. NPI and drug names remain strings.

- duplicate business keys: 0
- null business keys: 0
- invalid ten-digit NPIs: 0
- NPI, brand name, and generic name Parquet type: `VARCHAR`

## Encoding governance

The 2019 and 2021–2024 files decode strictly as UTF-8. The 2020 distribution
contains a non-UTF-8 byte sequence in the source city value for NPI
`1811527914`. That distribution is strictly decoded as Windows-1252 and
streamed to a temporary UTF-8 conversion input.

The resulting `Mayagãœez` value is preserved as upstream source evidence. It is
not silently corrected to the probable intended spelling. The verified raw CSV
and its acquisition receipt remain unchanged, and the temporary transcoded file
is removed after conversion.

## Numeric observations

All ten numeric candidates parse without invalid or negative values.

- total and age-65-or-older claim counts are integral;
- total and age-65-or-older days supplied are integral;
- beneficiary counts are integral when published;
- standardized 30-day fills and total drug cost remain decimal measures;
- the minimum published total claim count is 11.

The 11-claim minimum reflects CMS exclusion of prescriber-drug combinations
derived from 10 or fewer claims. Absence below this threshold is not zero
activity.

## Suppression semantics

CMS uses `*` for primary suppression and `#` for counter-suppression in the
age-65-or-older measures. Bronze retains both flags and null measure values.

- age-65-or-older claim-group suppressed rows: 69,849,579
- age-65-or-older beneficiary suppressed rows: 139,409,689
- flagged rows containing protected detail: 0
- unflagged rows missing corresponding protected detail: 0
- total beneficiary nulls retained: 88,567,432

Suppressed values are not reconstructed. Published zeroes remain distinct from
suppressed nulls.

## Cost interpretation

CMS total drug cost includes ingredient cost, dispensing fees, sales tax, and
applicable administration fees. It reflects amounts paid by Part D plans,
beneficiaries, government subsidies, and other third-party payers. It must not
be described as Medicare payment alone.

## Reconciliation and storage

For every year, raw CSV row count equals Bronze Parquet row count and annual
profile row count. All acquisition receipts remain valid. Raw CSV and generated
Parquet files remain excluded from Git; only governed configuration, technical
profiles, tests, and documentation are versioned.

## Analytical guardrails

- The data represents Medicare Part D, not all pharmacy activity.
- A benchmark deviation is not evidence of fraud, quality, or improper payment.
- Suppressed or excluded activity must not be imputed as zero.
- Brand and generic names are labels rather than NDC-level identifiers.
- Real prescribers remain separate from synthetic anomaly injection.
