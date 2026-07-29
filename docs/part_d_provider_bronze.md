# CMS Part D Prescriber Provider-Summary Bronze Dataset

## Purpose

This source family provides observed Medicare Part D prescribing, drug-cost,
beneficiary, coverage, opioid, antibiotic, antipsychotic, and prescriber
characteristics for synthetic pharmacy calibration and longitudinal pharmacy
cost intelligence.

It contains real aggregated Medicare activity but does not contain
claim-level pharmacy transactions or beneficiary identifiers.

## Source

| Property | Value |
|---|---|
| Publisher | Centers for Medicare & Medicaid Services |
| Dataset | Medicare Part D Prescribers by Provider |
| Reporting years | 2019–2024 |
| Source grain | One prescriber NPI per reporting year |
| Annual files | 6 |
| Raw size | Approximately 3.2 GiB |
| Bronze Parquet size | Approximately 994 MiB |
| Total rows | 7,913,081 |
| Source columns | 84 |
| Schema groups after normalization | 1 |

## Annual row counts

| Year | Rows | Bronze size |
|---:|---:|---:|
| 2019 | 1,240,595 | 149.14 MiB |
| 2020 | 1,255,175 | 149.42 MiB |
| 2021 | 1,287,454 | 153.34 MiB |
| 2022 | 1,332,309 | 159.13 MiB |
| 2023 | 1,380,665 | 164.86 MiB |
| 2024 | 1,416,883 | 170.63 MiB |

CSV, Parquet, and profile row counts reconcile exactly for every reporting
year.

## Governed schema normalization

CMS changed capitalization for two fields across releases:

| Source years | Observed column | Canonical bronze column |
|---|---|---|
| 2023–2024 | `PRSCRBR_NPI` | `Prscrbr_NPI` |
| 2019–2022 | `Prscrbr_Type_Src` | `Prscrbr_Type_src` |

The aliases are explicitly configured and tested. Raw CSV files remain
unchanged. Only the bronze Parquet schema is normalized.

After normalization, all six years have one consistent 84-column source
schema.

## Identifier validation

For every reporting year:

- row count equals distinct prescriber NPI count;
- null prescriber NPIs equal zero;
- invalid ten-digit NPIs equal zero;
- NPI is stored as `VARCHAR`.

NPI is never converted to a numeric type.

## Bronze design

The bronze conversion:

- requires a verified SHA-256 acquisition receipt;
- reads all source fields as strings;
- uses strict CSV parsing;
- preserves source nulls and suppression tokens;
- adds source ID, reporting year, source filename, and acquisition timestamp;
- writes Zstandard-compressed Parquet;
- generates annual technical profiles;
- generates a cross-year family inventory;
- detects ungoverned schema drift.

## Analytical coverage

The source supports observed benchmarks for:

- prescription claim volume;
- 30-day standardized fills;
- total drug cost;
- days supplied;
- beneficiary counts;
- brand, generic, and other drug categories;
- Medicare Advantage Part D and standalone PDP activity;
- low-income-subsidy and non-LIS activity;
- opioid and long-acting opioid measures;
- antibiotic measures;
- antipsychotic measures for beneficiaries aged 65 or older;
- beneficiary demographics and average risk score.

## Limitations

- The data represents Medicare Part D, not all pharmacy activity.
- Values are aggregated at prescriber-year grain.
- It does not contain individual drug events in this provider-summary source.
- Drug cost includes multiple payer and beneficiary components.
- Low-volume measures may be suppressed.
- Observed prescriber outliers are not proof of fraud or incorrect payment.
- Real NPIs will not receive injected synthetic anomalies.
- Pharmacy claim lifecycle events will be generated separately in the
  synthetic operational dataset.

## Outputs

Generated local outputs:

- six annual Parquet files under
  `data/processed/cms/cms_part_d_provider_summary/`;
- six annual JSON profiles under `data/metadata/profiles/`;
- one cross-year family inventory at
  `data/metadata/profiles/cms_part_d_provider_summary_family.json`.

Raw and processed healthcare files remain excluded from Git. Technical
metadata, governed configuration, tests, and documentation are versioned.