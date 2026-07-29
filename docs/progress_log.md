# Progress Log

## 2026-07-25 — Repository initialization and governance

### Completed

- Created an independent Git repository.
- Set `main` as the default branch.
- Created the public GitHub repository.
- Connected the local repository to `origin`.
- Pushed the initial project foundation.
- Established the feature-branch and pull-request workflow.
- Added the project plan, changelog, data-source strategy, and test strategy.
- Merged the project-governance pull request into `main`.

### Validation

- Repository root points to the healthcare project directory.
- Initial commit exists on local and remote `main`.
- GitHub repository visibility is public.
- GitHub default branch is `main`.
- Governance changes were reviewed through a pull request.
- Local and remote `main` were synchronized after the merge.

### Evidence

- Initial commit: `4d19f8e`
- Governance commit: `8451d16`
- Governance merge commit: `6577172`
- Pull request: `#1`
- Repository: `jangoansahasra/healthcare-claims-payment-integrity`

## 2026-07-25 — Continuous-integration foundation

### Completed

- Created the `feature/ci-foundation` branch.
- Created a project-local Python 3.12 environment.
- Installed the Python analytics and testing dependencies.
- Verified DuckDB, NumPy, pandas, PyArrow, SciPy, statsmodels, and PyYAML.
- Configured Ruff and pytest through `pyproject.toml`.
- Added six automated configuration tests.
- Added a GitHub Actions workflow for pushes and pull requests.
- Configured VS Code to use the project-local Python environment.

### Validation

- Python version: `3.12.13`
- Ruff: passed
- Pytest: 6 passed
- Configuration files: present and readable
- Payment-integrity rule IDs: unique and correctly formatted
- Rule severity, confidence, and required metadata: validated
- Project virtual environment: excluded from Git

### Current work

Reviewing and publishing the continuous-integration foundation through pull
request `#2`.

### Next task

Create a governed source manifest and reproducible ingestion process for
official CMS public-use datasets.

## 2026-07-25 — Current CMS source governance and discovery

### Completed

- Opened GitHub issue `#3` for current CMS data ingestion.
- Created the `feature/current-cms-data-ingestion` branch.
- Replaced legacy claim-line data as the primary source strategy.
- Registered six current observed and reference sources.
- Added freshness, privacy, publication, and licensing controls.
- Connected source discovery to the official CMS machine-readable catalog.
- Resolved 21 annual CMS distributions across 2019–2024.
- Recorded official resource identifiers, reporting periods, licenses, and
  download URLs.
- Added non-downloading remote-size probes.
- Added automated tests for the manifest, catalog, resolver, and source probes.

### Validation

- Ruff: passed
- Pytest: 31 passed
- Resolved CMS distributions: 21
- Professional medical detail: 17.37 GiB across six annual files
- Pharmacy detail: 21.06 GiB across six annual files
- Known combined source size: 38.43 GiB
- Inpatient and outpatient remote sizes: not exposed by the CMS server
- No complete healthcare CSV files were downloaded or committed

### Decision

Complete longitudinal coverage will use smaller CMS provider-level and
geographic summary products. Detailed provider/service and provider/drug data
will use reproducible current-year API cohorts. Inpatient and outpatient files
will be assessed independently before acquisition.

This preserves real national trend coverage while avoiding unnecessary local
copies of more than 38 GiB of detailed CSV data.

### Current work

Designing the tiered acquisition policy and API cohort specification.

### Next task

Register the smaller longitudinal CMS summary products and implement filtered,
paginated CMS API extraction.

## 2026-07-26 — Tiered CMS acquisition and bronze conversion

### Completed

- Expanded the governed source inventory to 34 CMS distributions.
- Added longitudinal physician-provider and Part D prescriber summaries.
- Added the Medicare Geographic Variation source covering 2014–2024.
- Documented full-download strategies and local disk-capacity controls.
- Implemented resumable streaming downloads with partial-file recovery.
- Implemented SHA-256 verification and machine-readable acquisition receipts.
- Implemented string-preserving CSV-to-Parquet conversion using Zstandard
  compression.
- Added technical Parquet profiles containing row counts, schemas, sizes, and
  checksums.
- Downloaded and converted the first official CMS source.

### Validation

- Ruff: passed
- Pytest: 47 passed
- Governed CMS distributions: 34
- Distributions with known remote sizes: 24
- Known planned source volume: 44.24 GiB
- Available local disk before acquisition: 219 GiB
- Geographic Variation source size: 57,865,948 bytes
- Geographic Variation source SHA-256:
  `10c8304012da34da3ecfe4caf4548927095f693383814d0e79ce6711b6806fad`
- Bronze Parquet rows: 36,994
- Bronze Parquet columns: 250
- Bronze Parquet size: 22.78 MiB
- Bronze Parquet SHA-256:
  `4b2963651406606e296321b08671acd9a2b000a6b9de8afe7d64e04fc7ca10bd`
- Source-year coverage: 2014–2024 inclusive
- Geography levels: National, State, and County
- Tested rows containing at least one suppression marker: 76
- Raw and processed healthcare files remain excluded from Git.

### Decision

CMS source values are preserved as strings in the bronze layer. Suppression
markers such as `*` are retained rather than converted to zero or silently
discarded. Type conversion, suppression flags, and analytical null handling
will be performed explicitly in the silver layer.

Complete national files will be acquired because the verified local disk
capacity supports the planned workload. Raw and processed datasets will remain
local or cloud-hosted and will not be committed to Git.

### Current work

Publishing the governed CMS acquisition and bronze-conversion framework.

### Next task

Create the typed and quality-tested silver model for Medicare Geographic
Variation data.

## 2026-07-27 — CMS Geographic Variation silver model

### Completed

- Defined the silver grain and four-field business key.
- Added stable identifiers for coded and aggregate geographies.
- Typed 23 count measures as `BIGINT`.
- Typed remaining analytical measures as `DECIMAL(38,6)`.
- Distinguished CMS suppression token `*` from not-applicable token `NA`.
- Created a long special-value lineage table.
- Added fail-fast validation for ungoverned numeric values.
- Added controlled end-to-end transformation tests.
- Built the real CMS Geographic Variation silver model.
- Generated a machine-readable quality report.

### Validation

- Ruff: passed
- Pytest: 64 passed
- Bronze rows: 36,994
- Silver rows: 36,994
- Typed measures: 241
- Duplicate business keys: 0
- Null business keys: 0
- Suppressed values: 686,853
- Not-applicable values: 806,938
- Special-value lineage rows: 1,493,791
- Count-range violations: 0
- Payment-range violations: 0
- Percentage-range violations: 0
- All nine silver quality checks passed.
- Wide and long special-value counts reconciled exactly.
- Generated Parquet files remain excluded from Git.

### Decision

Suppressed, not-applicable, and missing values are analytically distinct.
Suppressed and not-applicable values become null in the wide silver table while
their original token and status are retained in a separate lineage table.

Aggregate geographies without CMS codes use governed identifiers rather than
fabricated geographic codes.

### Current work

Publishing the typed and quality-tested geographic silver model.

### Next task

Complete the remaining governed CMS acquisitions and apply reusable bronze and
silver controls to each source family.

## 2026-07-27 — CMS physician provider-summary bronze family

### Completed

- Downloaded six official CMS provider-summary files for 2019–2024.
- Verified all six raw files using SHA-256 acquisition receipts.
- Added a reusable multi-year source-family converter.
- Added cross-year schema consistency and drift detection.
- Converted all annual files to Zstandard Parquet.
- Generated six annual technical profiles and one family inventory.
- Documented the physician provider-summary bronze dataset.

### Validation

- Ruff: passed
- Pytest: 71 passed
- Raw CSV volume: 2.7 GiB
- Bronze Parquet volume: 835 MiB
- Total provider-year rows: 7,302,541
- Reporting years: 2019–2024
- Source columns per year: 81
- Schema groups: 1
- CSV, Parquet, and profile row counts reconciled for every year.
- Rendering NPI is unique within every reporting year.
- Null rendering NPIs: 0
- Invalid rendering NPIs: 0
- Rendering NPI type: `VARCHAR`
- Raw and processed datasets remain excluded from Git.

### Decision

Provider identifiers and all other source values remain strings in bronze.
Typing, suppression handling, and historical provider-attribute treatment will
be implemented in the physician silver model.

### Current work

Publishing the physician provider-summary bronze acquisition.

### Next task

Create a typed, longitudinal physician provider silver model with explicit
provider identity, specialty, geography, utilization, payment, and beneficiary
risk fields.


## 2026-07-28 — CMS physician provider-summary silver model

### Completed

- Defined the longitudinal provider-year silver contract.
- Classified the source as an observed benchmark rather than claim-line data.
- Added explicit permitted and prohibited uses for real provider records.
- Typed 20 governed integer measures and 42 decimal measures.
- Preserved historical provider attributes by reporting year.
- Added provider-size classifications based on total beneficiaries.
- Preserved official CMS primary and counter-suppression semantics.
- Created long-form suppression lineage.
- Added per-metric and row-level chronic-condition top-coding indicators.
- Added country-safe geographic peer configuration.
- Created metric-level null summaries.
- Built the real six-year physician provider silver model.
- Generated a machine-readable quality report.
- Added controlled helper, contract, and end-to-end transformation tests.

### Validation

- Ruff: passed
- Pytest: 96 passed
- Bronze rows: 7,302,541
- Silver rows: 7,302,541
- Typed measures: 62
- Percentage metrics: 25
- Reporting years: 2019–2024
- Duplicate business keys: 0
- Null business keys: 0
- Invalid ten-digit NPIs: 0
- Null country codes: 0
- Primary suppression rows: 835,298
- Counter-suppression rows: 833,424
- Total suppression lineage rows: 1,668,722
- Top-coded chronic-condition cells: 9,602,567
- Unparseable numeric values: 0
- Numeric-range violations: 0
- Suppression-detail violations: 0
- All 23 silver quality checks passed.
- Generated Parquet outputs remain excluded from Git.

### Decision

The real CMS provider dataset is used only for observed benchmarking,
longitudinal trends, and synthetic-data calibration. It will not receive
injected anomalies and will not be used to label real providers as fraudulent
or incorrectly paid.

A value of 75 in a governed chronic-condition percentage field is treated as
75 percent or greater. It is preserved numerically while explicit top-coding
lineage prevents it from being interpreted as an exact percentage.

Country is required in peer definitions. US state and RUCA comparisons will
exclude foreign provider rows. Minimum-size peer eligibility will be built and
tested later in the benchmark gold layer.

### Current work

Publishing the governed physician provider-summary silver model.

### Next task

Acquire and transform the CMS Part D provider-summary family to establish the
pharmacy benchmark needed for medical-versus-pharmacy cost intelligence.

## 2026-07-29 — CMS Part D prescriber provider-summary bronze family

### Completed

- Downloaded six official CMS Part D provider-summary files for 2019–2024.
- Verified every raw file using its SHA-256 acquisition receipt.
- Detected two capitalization-only schema changes across CMS releases.
- Added governed, source-specific bronze column aliases.
- Preserved all raw CSV headers and values unchanged.
- Normalized the six annual Parquet files to one canonical schema.
- Generated six annual profiles and one family inventory.
- Added alias detection, collision, configuration, and integration tests.
- Documented the observed pharmacy benchmark and its limitations.

### Validation

- Ruff: passed
- Pytest: 102 passed
- Raw CSV volume: approximately 3.2 GiB
- Bronze Parquet volume: approximately 994 MiB
- Total prescriber-year rows: 7,913,081
- Reporting years: 2019–2024
- Source columns per year: 84
- Canonical schema groups: 1
- CSV, Parquet, and profile row counts reconciled for every year.
- Prescriber NPI is unique within every reporting year.
- Null prescriber NPIs: 0
- Invalid prescriber NPIs: 0
- Prescriber NPI type: `VARCHAR`
- Raw and processed datasets remain excluded from Git.

### Decision

Capitalization-only source drift is handled through explicit aliases configured
for this source family. Raw source files remain immutable; normalization occurs
only in bronze Parquet. Alias collisions fail instead of silently overwriting
a source column.

The real Part D data is used for observed pharmacy benchmarks and synthetic
calibration. It is not treated as claim-level data, and real prescribers will
not receive injected payment-integrity anomalies.

### Current work

Publishing the CMS Part D provider-summary bronze family.

### Next task

Profile Part D suppression behavior, numeric domains, cost measures, and
beneficiary fields before defining the longitudinal pharmacy silver contract.

## 2026-07-29 — CMS Part D prescriber silver model

### Completed

- Defined a governed longitudinal prescriber-year silver contract.
- Classified the real CMS data as an observed benchmark.
- Typed 37 integer and 19 decimal measures.
- Preserved year-specific prescriber attributes and acquisition lineage.
- Added explicit `Unknown` buckets and missing indicators for prescriber type
  and RUCA.
- Preserved all unflagged source nulls without zero imputation.
- Translated 11 CMS suppression indicators into semantic statuses.
- Created long-form primary and counter-suppression lineage.
- Added quartile-based prescriber-size bands and country-safe peer controls.
- Generated the production silver dataset and machine-readable quality report.
- Added contract, helper, and end-to-end transformation tests.

### Validation

- Ruff: passed
- Pytest: 132 passed
- Bronze rows: 7,913,081
- Silver rows: 7,913,081
- Typed measures: 56
- Reporting years: 2019–2024
- Duplicate business keys: 0
- Null business keys: 0
- Invalid ten-digit NPIs: 0
- Fractional integer violations: 0
- Numeric range violations: 0
- Invalid suppression tokens: 0
- Suppression-detail violations: 0
- Primary-suppression lineage rows: 16,923,033
- Counter-suppression lineage rows: 9,825,503
- Total suppression lineage rows: 26,748,536
- Source and lineage suppression totals reconcile exactly.
- Missing prescriber types preserved: 27
- Missing RUCA codes preserved: 8,977
- All 24 quality checks passed.
- Generated Parquet outputs remain excluded from Git.

### Decision

Suppressed values remain null and are never reconstructed. Unflagged nulls
remain source blanks with an unclassified reason rather than being treated as
zero or inferred suppression.

Real prescriber records support observed pharmacy benchmarking, longitudinal
trends, and synthetic calibration only. Benchmark outliers are not fraud
labels, and injected payment-integrity anomalies remain confined to the
separate synthetic insurer dataset.

### Current work

Publishing the governed CMS Part D prescriber silver model.

### Next task

Continue the M01 source roadmap with the next governed CMS provider-service
family, while retaining the same acquisition, bronze, silver, and quality
controls.

## 2026-07-29 — CMS inpatient provider-service bronze family

### Completed

- Downloaded six official CMS inpatient provider-service files for 2019–2024.
- Verified every raw file using its SHA-256 acquisition receipt.
- Identified Windows-1252 punctuation in the 2019–2023 source files.
- Added governed per-year source encodings and strict streaming transcoding.
- Preserved the raw files unchanged and normalized Bronze text to UTF-8.
- Added atomic Parquet replacement and temporary-file cleanup.
- Converted all six annual files to Zstandard Parquet.
- Generated six annual technical profiles and one family inventory.
- Reconciled provider-DRG business keys and identifier formats.

### Validation

- Ruff: passed
- Pytest: 136 passed
- Raw CSV volume: 232 MiB
- Bronze Parquet volume: 18 MiB
- Total provider-DRG-year rows: 936,131
- Reporting years: 2019–2024
- Source columns per year: 15
- Schema groups: 1
- CSV, Parquet, and profile row counts reconcile for every year.
- Duplicate business keys: 0
- Null business keys: 0
- Invalid six-character CCNs: 0
- Invalid three-digit DRG codes: 0
- Unparseable numeric candidates: 0
- Fractional discharge values: 0
- Medicare-payment-above-total-payment rows: 0
- Raw files remain receipt-valid after conversion.

### Decision

Source encoding is governed by year. Windows-1252 files are decoded strictly
and streamed to temporary UTF-8 inputs; malformed data fails conversion.
Ignoring decode errors or modifying receipt-governed raw files is prohibited.

The 1,915 observed rows where average total payment exceeds average submitted
covered charge are retained. This relationship is not a Bronze rejection rule
and will be documented and profiled before any Silver interpretation.

### Current work

Publishing the CMS inpatient provider-service Bronze family.

### Next task

Define a typed inpatient provider-DRG Silver model with explicit geographic,
discharge, charge, and payment semantics.
