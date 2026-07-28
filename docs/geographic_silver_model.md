# CMS Geographic Variation Silver Model

## Purpose

The silver model converts the string-preserving Medicare Geographic Variation
bronze dataset into typed, analysis-ready data without losing information about
CMS suppression or not-applicable values.

The model supports geographic cost, utilization, demographic, and provider-mix
benchmarking. It does not represent claim-line transactions or individual
beneficiaries.

## Source

- Publisher: Centers for Medicare & Medicaid Services
- Dataset: Medicare Geographic Variation by National, State, and County
- Included years: 2014–2024
- Geography levels: National, State, and County
- Bronze rows: 36,994
- Source measures: 241
- Direct beneficiary identifiers: none

## Silver analytical table

Path:

`data/interim/silver/cms_geographic_variation.parquet`

The file is generated locally and excluded from Git.

### Grain

One row per:

- year;
- geography level;
- normalized geography;
- beneficiary age level.

### Business key

- `year`
- `geography_level`
- `geography_id`
- `beneficiary_age_level`

The validated business key is unique and non-null for all 36,994 rows.

### Geography identifiers

| Source condition | Silver geography identifier |
|---|---|
| National / National / null code | `US` |
| State / Territory / null code | `AGG_TERRITORY` |
| State / ZZ / null code | `AGG_ZZ` |
| Coded state | `STATE:<source code>` |
| Coded county | `COUNTY:<source code>` |

The source geography code remains a string so leading zeroes are preserved.

### Type rules

- `year`: `INTEGER`
- source measures ending in `_CNT`: `BIGINT`
- other analytical measures: `DECIMAL(38,6)`
- geography and lineage fields: `VARCHAR`
- `TRY_CAST` is used only after governed special values are removed
- ungoverned nonnumeric values cause the transformation to fail

## Special-value lineage table

Path:

`data/interim/silver/cms_geographic_variation_value_status.parquet`

The file is generated locally and excluded from Git.

The main analytical table converts governed special values to null. A separate
long table preserves why each value became null.

| Source token | Status | Analytical value |
|---|---|---|
| `*` | `suppressed` | null |
| `NA` | `not_applicable` | null |
| empty string | missing | null |

The lineage table contains the silver business key, measure name, original
source token, and value status.

Validated counts:

- Suppressed values: 686,853
- Not-applicable values: 806,938
- Total special-value lineage rows: 1,493,791

Counts in the wide silver table reconcile exactly to the long lineage table.

## Retained lineage

- `_source_id`
- `_reporting_year`
- `_source_file`
- `_acquired_at_utc`

## Quality controls

The build fails for:

- missing bronze input;
- ungoverned nonnumeric measure values;
- duplicate or null business keys;
- lost source rows;
- missing source years or geography levels;
- negative counts;
- negative payment amounts;
- percentages outside zero through one hundred.

## Validation results

| Check | Result |
|---|---:|
| Bronze rows | 36,994 |
| Silver rows | 36,994 |
| Typed measures | 241 |
| Years retained | 11 |
| Duplicate business keys | 0 |
| Null business keys | 0 |
| Count-range violations | 0 |
| Payment-range violations | 0 |
| Percentage-range violations | 0 |
| Automated test suite | 64 passed |
| All silver quality checks | Passed |

Machine-readable validation evidence is stored in:

`data/metadata/quality/cms_geographic_variation_silver.json`

## Limitations

- The dataset represents Original Medicare fee-for-service activity.
- It is aggregated public-use data, not claim-line data.
- Suppressed values must never be interpreted as zero.
- Not-applicable values are analytically different from suppressed values.
- Geographic results may reflect population mix and program composition.
- The latest distribution contains historical years and is not real-time data.
