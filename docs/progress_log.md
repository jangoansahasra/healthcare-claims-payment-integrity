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

## 2026-07-30 — CMS inpatient provider-DRG silver model

### Completed

- Defined a governed hospital CCN, MS-DRG, and reporting-year contract.
- Verified charge and payment semantics against official CMS definitions.
- Typed total discharges as `BIGINT` and three financial measures as
  `DECIMAL(38,6)`.
- Preserved hospital and DRG descriptions as year-specific attributes.
- Added explicit RUCA missing indicators and `Unknown` analytical buckets.
- Added quartile-based discharge-volume bands.
- Added an observed total-payment-above-covered-charge indicator.
- Enforced Medicare payment not exceeding total payment.
- Generated the production Silver dataset and quality report.
- Added contract, helper, and end-to-end builder tests.

### Validation

- Ruff: passed
- Pytest: 165 passed
- Bronze rows: 936,131
- Silver rows: 936,131
- Typed measures: 4
- Reporting years: 2019–2024
- Duplicate or null business keys: 0
- Invalid CCNs, DRGs, state FIPS codes, or ZIP codes: 0
- Fractional or below-threshold discharges: 0
- Negative discharge or financial values: 0
- Medicare-payment-above-total-payment rows: 0
- Total-payment-above-covered-charge rows retained: 1,915
- Missing RUCA code and description rows: 681 each
- All 21 quality checks passed.
- Generated Silver Parquet remains excluded from Git.

### Decision

Average total payment includes Medicare, beneficiary cost sharing, and
third-party coordination-of-benefits amounts. Average Medicare payment is the
Medicare share, so Medicare payment may not exceed total payment.

Covered charge is a hospital charge rather than an expected-payment ceiling.
The 1,915 total-payment-above-charge rows are retained and flagged rather than
rejected.

CMS reports the literal description `Unknown` for RUCA code `99`. Missing RUCA
values also receive an `Unknown` analytical bucket, so missingness must be
determined from the explicit Boolean indicator rather than the label.

### Current work

Publishing the governed inpatient provider-DRG Silver model.

### Next task

Continue M01 with the next provider-service family while preserving the same
governed acquisition, Bronze, Silver, and quality controls.

## 2026-07-31 — CMS outpatient provider-service Bronze family

### Completed

- Downloaded and receipt-validated all configured published periods: 2019,
  2021, and 2023.
- Governed strict Windows-1252 decoding for 2019 and 2021 and UTF-8 decoding
  for 2023 without modifying raw source files.
- Converted all three distributions to Zstandard Parquet.
- Generated three annual technical profiles and one family inventory.
- Verified a single consistent 18-column source schema.
- Preserved CCN and APC identifiers as strings.
- Documented unavailable periods rather than interpolating them.

### Validation

- Raw CSV volume: 81 MiB
- Bronze Parquet volume: 5.5 MiB
- Total provider-APC-period rows: 350,393
- CSV, Parquet, and profile counts reconcile for every period.
- Duplicate or null business keys: 0
- Identifier-format violations: 0
- Nonnumeric tokens: 0
- Fractional count values: 0
- Missing RUCA code and description rows: 18 each
- All raw source files remain receipt-valid after conversion.

### Decision

The published 2019, 2021, and 2023 periods form an available-period series,
not a complete annual panel. Missing years will not be synthesized,
interpolated, or interpreted as zero activity.

Numeric source nulls remain null in Bronze. Their suppression,
non-applicability, and publication semantics must be verified against official
CMS definitions before the Silver contract is finalized.

### Current work

Publishing the CMS outpatient provider-service Bronze family.

### Next task

Define a typed outpatient hospital-APC Silver model with explicit missingness,
charge, allowed-amount, payment, and outlier semantics.

## 2026-07-31 — CMS outpatient hospital-APC Silver model

### Completed

- Defined a governed hospital CCN, comprehensive APC, and published-period
  contract using official CMS definitions.
- Typed three count and four monetary measures without null imputation.
- Added independent provider-APC summary, beneficiary-count, and outlier-detail
  suppression statuses.
- Preserved period-specific hospital and APC attributes.
- Added explicit RUCA missing indicators and service-volume bands.
- Enforced Medicare payment not exceeding allowed amount.
- Retained and reported valid submitted-charge and outlier relationships.
- Generated the production Silver dataset and machine-readable quality report.
- Added contract, helper, and end-to-end builder tests.

### Validation

- Ruff and Ruff formatting: passed
- Pytest: 189 passed
- Bronze and Silver rows: 350,393 each
- Typed measures: 7
- Published periods: 2019, 2021, and 2023
- Provider-APC summary suppressions: 157,739
- Beneficiary-count suppressions: 161,089
- Outlier-detail suppressions: 211,218
- Invalid identifiers, fractional counts, and negative values: 0
- Medicare-payment-above-allowed violations: 0
- Allowed-above-submitted-charge rows retained: 85
- Payment-above-submitted-charge rows retained: 49
- Outlier-above-regular-payment rows retained: 3,082
- All 26 quality checks passed.

### Decision

CMS suppression rules operate independently at the provider-APC summary,
beneficiary-count, and outlier-detail levels. Silver preserves those states
explicitly and prohibits reconstruction or zero imputation.

Medicare payment may not exceed allowed amount. Submitted charge is not a
payment ceiling, and outlier payments are separate from regular payments, so
those observed comparisons are reported rather than rejected.

### Current work

Publishing the governed outpatient hospital-APC Silver model.

### Next task

Continue M01 with the physician provider-service acquisition family using the
same reproducibility, typing, suppression, and observed-benchmark controls.

## 2026-08-01 — CMS physician provider-service Bronze family

### Completed

- Downloaded and receipt-validated all six 2019–2024 distributions.
- Verified one stable 28-column CMS schema with strict UTF-8 decoding.
- Converted 58,673,513 rows to Zstandard Parquet.
- Generated six annual technical profiles and one family inventory.
- Preserved NPI, HCPCS, place-of-service, and all source values as strings.
- Reconciled CSV, Parquet, and profile row counts for every year.
- Profiled numeric types, publication thresholds, payment relationships, and
  missing provider geography.

### Validation

- Raw CSV volume: 17.4 GiB
- Bronze Parquet volume: 1.9 GiB
- Duplicate or null business keys: 0
- Invalid NPIs or HCPCS codes: 0
- Nonnumeric measure tokens: 0
- Fractional beneficiary or beneficiary-day counts: 0
- Fractional total-service rows retained: 55,901
- Medicare-payment-above-allowed rows: 0
- All source receipts remain valid after conversion.

### Decision

Total services is not governed as an integer because HCPCS-specific unit
definitions produce legitimate fractional values. Beneficiary and
beneficiary-day counts remain integer candidates.

Submitted charge is not a payment ceiling, and standardized payment is an
adjusted comparison measure rather than a component of allowed amount.
Observed cross-measure exceptions are retained for Silver reporting.

### Current work

Publishing the CMS physician provider-service Bronze family.

### Next task

Define a typed provider-HCPCS-place-of-service Silver model with explicit
publication thresholds, country-safe geography, service-unit semantics, and
peer-comparison governance.

## 2026-08-01 — CMS physician provider-service Silver model

### Completed

- Defined a governed NPI, HCPCS, place-of-service, and reporting-year contract.
- Typed seven measures while preserving fractional HCPCS service units.
- Added beneficiary-volume bands and country-safe peer geography.
- Preserved provider attributes and HCPCS descriptions by reporting year.
- Added explicit state-FIPS and RUCA missing indicators.
- Enforced Medicare payment not exceeding allowed amount.
- Retained submitted-charge and standardized-payment comparison exceptions.
- Added atomic production Parquet replacement and machine-readable quality reporting.
- Added contract, helper, and end-to-end builder tests.

### Validation

- Ruff and Ruff formatting: passed
- Pytest: 204 passed
- Bronze and Silver rows: 58,673,513 each
- Typed measures: 7
- Fractional total-service rows retained: 55,901
- Missing state-FIPS rows: 6,134
- Missing RUCA-code rows: 41,175
- Invalid keys, identifiers, domains, or negative measures: 0
- Medicare-payment-above-allowed violations: 0
- Foreign peer-geography violations: 0
- All 24 quality checks passed.
- Silver Parquet size: 1.7 GiB
- Available disk after build: 187 GiB

### Decision

Total services remains decimal because CMS counting metrics vary by service.
Standardized Medicare payment is a geographic adjustment for comparison and
is not treated as a payment component or constrained below allowed amount.

State and RUCA peer dimensions apply only to U.S. providers. Foreign-provider
comparisons use country and explicit `Not applicable` domestic geography.

### Current work

Publishing the governed physician provider-service Silver model.

### Next task

Reassess M01 completeness before acquiring another large source family, then
prioritize synthetic claims, Gold payment-integrity models, and business-facing
analytics when the benchmark foundation is sufficient.

## 2026-08-02 — CMS Part D provider-drug Bronze family

### Completed

- Downloaded and receipt-validated all six 2019–2024 CMS distributions.
- Verified one consistent 22-column source schema across all years.
- Converted 156,531,752 records to Zstandard Parquet.
- Generated six annual technical profiles and one family inventory.
- Preserved NPI, brand name, generic name, and source lineage as strings.
- Governed strict CP1252 transcoding for the anomalous 2020 distribution while
  leaving the receipt-governed raw file unchanged.
- Reconciled raw CSV, Bronze Parquet, and profile counts for every year.

### Validation

- Raw CSV volume: 21 GiB
- Bronze Parquet volume: 2.9 GiB
- Duplicate or null business keys: 0
- Invalid ten-digit NPIs: 0
- Invalid or negative numeric values: 0
- Fractional integer-candidate values: 0
- Minimum total claim count: 11
- Suppression/detail reconciliation violations: 0
- Available disk after conversion: 164 GiB

### Decision

The governed grain is prescriber NPI, brand name, generic name, and reporting
year. Total drug cost is an aggregate across plan, beneficiary, subsidy, and
other third-party amounts; it is not labeled as Medicare payment.

Primary and counter-suppressed measures remain null with their source flags.
The observed 2020 `Mayagãœez` value is retained as a documented upstream
encoding defect rather than silently corrected.

### Current work

Publishing the governed CMS Part D provider-drug Bronze family.

### Next task

Confirm M01 ingestion exit criteria and define whether drug-level Silver is
required before beginning synthetic claim-lifecycle and Gold analytics work.

## 2026-08-02 — Synthetic operational data contract

### Completed

- Closed M01 after all public-data ingestion exit criteria were satisfied.
- Started M02 with a versioned contract for 14 synthetic operational tables.
- Defined every table grain, primary key, foreign key, and core column type.
- Aligned the contract to the existing deterministic seed, reporting window,
  policy date, population sizes, currency, and partition controls.
- Defined claim-version history and append-only adjudication, payment, and
  recovery ledgers.
- Defined explicit utilization, operations, finance, and eligibility date roles.
- Added fixed-decimal financial conventions and eight reconciliation rules.
- Added privacy, calibration, publication, and Git-storage controls.
- Added structural tests for keys, references, dates, financial types, and
  M02/M03 separation.

### Decision

M02 produces a clean operational baseline. Intentional payment-integrity
anomalies and their ground truth remain the responsibility of M03.

The existing 2025-01-01 through 2026-06-30 window is retained. It provides 12
pre-policy months and six post-policy months around the 2026-01-01 simulated
policy start date.

Claim adjustments and resubmissions create linked versions; they never replace
history. Net paid amount is derived from signed append-only transactions.

### Current work

Publishing the synthetic operational data contract and lifecycle documentation.

### Next task

Implement deterministic generation of synthetic dimensions, eligibility, clean
claims, adjudication events, and financial transactions from this contract.

## 2026-08-02 — Synthetic dimensions and eligibility

### Completed

- Added stable SHA-256-derived generation without mutable global random state.
- Generated 10,000 members, four plans, 200 providers, 800 provider contracts,
  158,746 membership-month rows, and 200 policy assignments.
- Derived Arrow schemas directly from the versioned operational contract.
- Added atomic Zstandard Parquet output and small synthetic-only CSV samples.
- Added canonical content hashes and a machine-readable quality report.
- Added deterministic unit, integration, schema, relationship, and repeat-build
  tests.

### Validation

- Machine-readable quality checks: 45 passed
- Policy cohorts: 88 treated and 112 comparison providers
- Eligibility periods: 18 distinct months from January 2025 through June 2026
- Members represented in eligibility: 10,000
- Medicare Advantage member ages at baseline: 65–85
- Facility providers represented as individuals: 0
- Primary-key, foreign-key, identifier, date, and schema violations: 0
- Full generated Parquet size: approximately 152 KiB

### Decision

Deterministic choices are derived from the configured seed, entity namespace,
and row number through SHA-256. This avoids order-dependent random state and
supports stable content hashes and repeatable Parquet bytes.

Medicare Advantage assignment is limited to members aged 65 or older at the
reporting-period start. Inpatient and outpatient facility specialties are
always synthetic organizations. No real member or provider record is copied.

### Current work

Publishing deterministic M02 dimensions and eligibility.

### Next task

Generate the clean claim header, claim line, adjudication event, denial, and
payment-transaction baseline using these validated dimensions.

## 2026-08-03 — Clean synthetic claim lifecycle

### Completed

- Generated 75,000 immutable claim-header versions across professional,
  inpatient, outpatient, and pharmacy claim types.
- Generated 177,206 claim lines, 150,000 adjudication events, 68,877 payment
  transactions, and 6,123 ordinary denial outcomes.
- Linked every claim to active service-month eligibility and an applicable
  synthetic provider-plan contract.
- Preserved fractional pharmacy units and fixed-decimal financial values.
- Added linked second claim versions with stable identity and service fields.
- Added atomic Parquet output, deterministic content hashes, committed
  synthetic-only samples, and a machine-readable quality report.

### Validation

- Machine-readable quality checks: 92 passed
- Claim types: 38,840 professional; 7,530 inpatient; 15,097 outpatient; 13,533 pharmacy
- Claim statuses: 65,671 paid; 3,206 adjusted; 6,123 denied
- Header/line financial reconciliation violations: 0
- Payment reconciliation violations: 0
- Eligibility and provider-contract violations: 0
- Claim-version identity and sequencing violations: 0
- Denied claims with positive payment: 0
- Full generated synthetic Parquet volume: approximately 6.3 MiB

### Decision

Ordinary clean-baseline denials set allowed amount and member liability to zero
and create no payment transaction. Version-two claims retain the member, plan,
provider, claim type, service dates, and logical claim identity of version one.

M02 continues to exclude intentional payment-integrity anomalies and labels.

### Current work

Publishing the clean synthetic claim lifecycle.

### Next task

Generate clean review, audit, and recovery workflow records, then close the M02
operational baseline after end-to-end reconciliation.

## 2026-08-03 — Synthetic review, audit, and recovery workflow

### Completed

- Generated 3,748 deterministic completed claim-review episodes.
- Generated one clean audit outcome for every completed review.
- Produced a fully typed zero-row recovery-transaction Parquet table.
- Validated all 14 governed operational tables together.
- Added canonical content hashes, synthetic-only samples, and a machine-readable
  end-to-end quality report.
- Marked M02 complete in the project plan while retaining the explicit M03
  anomaly-injection boundary.

### Validation

- End-to-end machine-readable quality checks: 113 passed
- Clean audit outcomes: 3,140 no issue; 608 inconclusive
- Confirmed improper-payment amounts: 0
- Recovery transactions: 0
- Review, audit, key, relationship, and date violations: 0
- Claim and payment reconciliation violations: 0
- Governed operational tables with typed Parquet output: 14 of 14

### Decision

The clean baseline has no confirmed improper-payment findings, so its recovery
ledger is intentionally empty. The zero-row Parquet retains its full contract
schema for downstream compatibility.

Review selection is operational activity, not an anomaly label. Confirmed
overpayments, recoveries, and ground-truth labels remain isolated to M03.

### Current work

Publishing the final M02 operational workflow and completion evidence.

### Next task

Begin M03 controlled anomaly injection only after the M02 parent issue is
reviewed and closed.

## 2026-08-03 — Controlled anomaly and ground-truth contract

### Completed

- Started M03 after closing the fully reconciled M02 clean baseline.
- Defined explicit injection semantics for PI001 through PI010.
- Defined anomaly-injection, field-change, and baseline-hash-manifest grains,
  keys, columns, and identifier formats.
- Defined deterministic eligibility, exclusion, mutation, and financial-
  exposure semantics for every scenario.
- Defined claim, line, payment-transaction, provider, and provider-period label
  scopes.
- Prohibited overlap by default and governed the two permitted multi-label
  combinations with required overlap groups.
- Added privacy, clean-baseline immutability, output-isolation, and publication
  controls.
- Added automated contract, registry-alignment, lineage, baseline-hash,
  identifier, overlap, privacy, and storage-policy tests.

### Decision

Anomaly generation writes to `data/generated/synthetic_anomalous/` and never
edits the clean M02 files. Baseline content hashes are verified before and after
injection.

Every mutation retains typed before-and-after lineage. Expected exposure may be
zero for suspicious integrity conditions that do not establish a deterministic
overpayment amount.

M03 ground truth is synthetic evaluation truth, not evidence of fraud or a
finding against a real provider.

### Current work

Publishing the M03 anomaly-injection and ground-truth contracts.

### Next task

Implement deterministic baseline cloning, hash-manifest generation, and the
first bounded group of record-level anomaly scenarios.

## 2026-08-03 — Record-level anomaly injection

### Completed

- Cloned all 14 clean M02 Parquet tables into the isolated anomalous output root.
- Generated a baseline manifest with row counts, content hashes, schema hashes,
  and contract lineage.
- Injected 50 instances each of PI001, PI002, PI005, and PI006.
- Generated 200 anomaly-instance labels and 1,700 typed field-change records.
- Added deterministic target ranking and prohibited overlap across all selected
  claims.
- Added atomic anomalous Parquet output, synthetic-only samples, and a
  machine-readable quality report.
- Added reduced end-to-end repeat-build tests covering output hashes and Parquet
  bytes.

### Validation

- Record-level injection quality checks: 29 passed
- Unique anomaly injections: 200
- Disjoint target claims: 200
- PI001 expected exposure: $44,821.43
- PI002 expected exposure: $158,584.83
- PI005 expected exposure: $500.00
- PI006 expected exposure: $500.00
- Baseline hash changes before or after injection: 0
- Unintended PI005 header mismatches: 0
- Unintended PI006 excess-payment conditions: 0
- Full isolated anomalous output volume: approximately 6.4 MiB

### Decision

Duplicate-line scenarios update related synthetic header and payment totals so
their intended condition remains duplicate behavior rather than an accidental
reconciliation failure. PI005 and PI006 modify only their governed header or
ledger field.

Existing lines and non-targeted headers and payments remain equal to M02. All
other tables retain their clean baseline Parquet bytes.

### Current work

Publishing the first controlled M03 record-level anomaly group.

### Next task

Implement PI003 and PI004 payment-ledger and temporal anomalies with isolated
ground truth and baseline-preservation checks.

## 2026-08-03 — Payment-ledger and temporal anomaly injection

### Completed

- Added a composable stage that deterministically rebuilds the prior anomaly
  group before applying new mutations.
- Injected 50 PI003 unresolved-payment-after-reversal scenarios.
- Injected 50 PI004 impossible-payment-date scenarios.
- Appended 100 payment transactions as full reversal and unresolved repayment
  pairs.
- Preserved the existing 200 labels and extended field lineage from 1,700 to
  2,450 rows.
- Added dedicated PI003/PI004 samples and a machine-readable quality report.
- Added reduced end-to-end repeat-build tests for combined ground truth and
  anomalous payment Parquet bytes.

### Validation

- Ledger-temporal quality checks: 26 passed
- Total controlled injections: 300
- PI003 expected exposure: $95,057.12
- PI004 expected exposure: $0.00
- Invalid reversal references or amounts: 0
- Nonmonotonic PI003 transaction sequences: 0
- PI004 payment-amount changes: 0
- Prior or cross-scenario target overlaps: 0
- Clean M02 baseline hash changes: 0

### Decision

PI003 exposure is the positive repayment remaining after a full reversal. PI004
is a zero-dollar integrity condition because impossible payment timing does not
alone establish an overpayment amount.

The composed builder writes its internal prerequisite report beneath the ignored
anomalous output root, avoiding unrelated changes to committed stage evidence.

### Current work

Publishing the PI003 and PI004 anomaly extension.

### Next task

Implement provider-amount and provider-period anomalies PI007 and PI008 with
governed peer groups and time-series baselines.

## 2026-08-03 — Provider amount and utilization anomaly injection

### Completed

- Injected 50 PI007 provider amount outliers above governed
  specialty/service-system peer thresholds.
- Injected 50 PI008 provider-period utilization surges using complete copied
  claim, line, adjudication, and payment lifecycles.
- Preserved all 300 prior labels and prohibited overlap with prior targets.
- Added complete before-and-after lineage for 143,257 field changes.
- Added dedicated samples, a machine-readable quality report, and focused
  deterministic unit and composed-build tests.

### Validation

- Provider-pattern quality checks: 25 passed
- Total controlled injections: 400
- PI007 expected exposure: $339,437.25
- PI008 expected exposure: $14,195,769.67
- Invalid eligibility or provider-contract relationships: 0
- Header-line or payment reconciliation violations: 0
- Duplicate generated identifiers: 0
- Cross-scenario target overlaps: 0
- Clean M02 baseline hash changes: 0

### Decision

PI007 raises allowed amounts beyond 1.25 times the observed peer maximum while
preserving the original charge ratio, member-liability relationship, header
totals, and payment reconciliation. PI008 measures historical utilization only
from pre-policy months and inserts positively paid, contract-valid lifecycle
copies until the provider-period count strictly exceeds three times its
historical monthly average.

### Current work

Publishing the PI007 and PI008 provider-pattern anomaly extension.

### Next task

Implement PI009 excessive procedure repetition and PI010
diagnosis-procedure incompatibility, then complete M03 end-to-end ground-truth
validation.

## 2026-08-04 — Procedure-frequency and clinical-compatibility anomalies

### Completed

- Added explicit claim/service-code repetition ceilings for professional and
  outpatient services.
- Added governed diagnosis and procedure category mappings with deterministic
  incompatible replacement codes.
- Injected 50 PI009 excessive procedure-frequency anomalies while preserving
  claim and payment reconciliation.
- Injected 50 PI010 diagnosis-procedure incompatibilities without changing
  service, adjudication, payment, or exposure values.
- Preserved all 400 prior labels and prohibited overlap with prior targets.
- Completed the M03 ten-rule dataset with 500 labels and 145,547 field-lineage
  rows.

### Validation

- Final-stage quality checks: 24 passed
- PI009 expected exposure: $78,308.43
- PI010 expected exposure: $0.00
- Invalid repetition-limit outcomes: 0
- Invalid diagnosis-procedure compatibility outcomes: 0
- Header-line or payment reconciliation violations: 0
- Missing mutation lineage: 0
- Cross-scenario overlaps: 0
- Clean M02 baseline hash changes: 0
- Deterministic focused and composed-build tests passed

### Decision

PI009 exposure equals the inserted repeated lines' net paid amounts. PI010 is a
zero-dollar integrity condition because clinical incompatibility alone does not
establish an overpayment. Clinical mappings are deliberately small, explicit,
synthetic evaluation controls and are not production coverage policy.

### Current work

Publishing the final PI009/PI010 increment and M03 completion evidence.

### Next task

Begin M04 by building the reconciled trusted claims dimensional model. M05 can
then execute the ten explainable rules against the complete M03 ground truth.

## 2026-08-04 — Trusted claims dimensional contract

### Completed

- Defined five conformed dimensions, five analytical facts, and two governed
  bridges for the M04 trusted model.
- Preserved every claim version while requiring exactly one deterministic
  current version per logical claim.
- Defined stable integer surrogate keys without discarding synthetic business
  identifiers.
- Assigned explicit service, adjudication, payment, review, coverage, and
  policy date roles.
- Separated M03 ground truth into an evaluation-only bridge prohibited from
  ordinary model features.
- Added curated-output Git exclusion and automated contract, key, type,
  reconciliation, privacy, and storage-control tests.
- Recorded Looker Studio as the primary portfolio dashboard and Power BI as a
  compact independent KPI-validation deliverable.

### Decision

Default financial reporting uses current claim versions only; all versions
remain available for operational history. Net paid is always derived from the
append-only signed transaction ledger. Claim anomaly truth is joined only for
evaluation and never embedded in the ordinary claim fact.

### Current work

Publishing the versioned trusted-claims contract.

### Next task

Generate and reconcile the twelve trusted dimensional tables as deterministic
typed Parquet with machine-readable quality evidence and synthetic samples.

## 2026-08-04 — Trusted claims dimensional model generation

### Completed

- Generated all twelve contract-conforming trusted dimensions, facts, and
  bridges from the isolated PI001–PI010 anomalous dataset.
- Assigned deterministic surrogate keys while preserving source business IDs.
- Retained 77,095 claim versions and marked 73,606 deterministic current
  versions.
- Derived ledger-based claim net paid and line-based plan-paid measures.
- Resolved 182,348 claim lines, 71,072 payment transactions, 3,748 reviews, 200
  policy assignments, and all 500 anomaly labels.
- Published a machine-readable quality report and twelve 25-row synthetic-only
  samples while keeping full curated Parquet outside Git.

### Validation

- Trusted tables: 12
- Machine-readable quality checks: 67 passed
- Primary or natural-key violations: 0
- Unresolved dimension, fact, self-reference, date, or bridge foreign keys: 0
- Logical claims without exactly one current version: 0
- Ungoverned header-line reconciliation mismatches: 0
- Ledger net-paid reconciliation violations: 0
- Current denied claims with positive payment: 0
- Service-date eligibility violations: 0
- Missing anomaly labels: 0
- Full trusted output volume: approximately 8.7 MiB

### Decision

The trusted model uses the isolated anomalous evaluation variant so M05 can
measure rule performance, but labels remain available only through the
evaluation bridge. Ordinary claim and line facts contain no rule IDs or ground
truth exposure.

### Current work

Publishing the reconciled M04 dimensional model and completion evidence.

### Next task

Begin M05 with versioned explainable rule-output and evaluation contracts, then
run the ten governed rules against the trusted model and 500-label ground truth.

## 2026-08-04 — Payment-integrity engine and evaluation contract

### Completed

- Defined a standard explainable finding schema for all ten PI001–PI010 rules.
- Added sequenced evidence lineage with observed values, comparison operators,
  thresholds, and source-record references.
- Separated rules execution from ground-truth evaluation and required findings
  to be frozen before labels can be read.
- Defined exact canonical matching for claim, claim-line, transaction,
  provider, and provider-period labels, including per-rule multi-label handling.
- Defined auditable match rows, rule-level and overall confusion matrices,
  precision, recall, false-positive rate, exposure recall, and pass thresholds.
- Added deterministic Parquet, privacy, publication, and quality-check controls.

### Decision

The rules engine may read ordinary trusted dimensions and facts only. The M03
anomaly bridge is opened exclusively by the post-detection evaluator. A review
lead is never presented as proof of fraud or a finding against a real provider.

### Current work

Publishing the versioned M05 rule-output and evaluation contract.

### Next task

Implement deterministic PI001–PI010 detection, freeze explainable findings,
then evaluate them against the isolated 500-label ground-truth bridge.

## 2026-08-04 — Payment-integrity engine execution and evaluation

### Completed

- Executed all ten governed rules against ordinary trusted facts and dimensions.
- Published 500 frozen findings and sequenced supporting-evidence rows.
- Opened the isolated anomaly bridge only after hashing the final finding set.
- Evaluated all 500 controlled labels using exact rule, scope, and canonical
  target matching.
- Published five typed Parquet outputs, synthetic-only samples, and a
  machine-readable quality report while keeping full outputs outside Git.
- Verified deterministic content hashes and Parquet bytes across repeated runs.

### Validation

- True positives: 440
- False positives: 60
- False negatives: 60
- Precision: 88.0%
- Recall: 88.0%
- False-positive rate: 0.01%
- All 24 machine-readable quality checks passed
- Detection-phase ground-truth access: false

### Decision

The overall portfolio thresholds pass, but rule-level limitations remain
visible. PI010 clinical compatibility achieved only 2% precision and recall
because its deliberately small synthetic mapping also describes many ordinary
claims. It remains a low-confidence review lead and is not suitable for
production clinical or payment decisions.

### Current work

Publishing M05 engine implementation and measured evaluation evidence.

### Next task

Complete M05, then begin M06 cost intelligence using current-version trusted
claims, eligible member-month denominators, and explicit service/payment dates.

## 2026-08-04 — M05 clean-runner CI reproducibility correction

### Finding

The first merged M05 implementation passed locally but failed on three GitHub
Actions triggers because its integration tests read ignored trusted Parquet
available only in the local workspace. The failures corresponded to the branch
push, pull-request event, and merge push to `main`.

### Correction

- Made the trusted integration-test root configurable by environment variable.
- Added a CI setup step that reproducibly builds clean synthetic operations,
  controlled anomalies, and the trusted model in the runner temporary folder.
- Preserved the rule that full generated and curated data remain outside Git.
- Reopened issue #58 until the corrected workflow passes on GitHub Actions.

## 2026-08-04 — M06 cost-intelligence metric contracts

### Completed

- Defined five versioned analytical outputs covering service-month cost and
  utilization, payment-month cash flow, concentration, cost-change
  decomposition, and early-warning signals.
- Governed allowed and paid PMPM plus claim and unit utilization per 1,000
  using active eligible member-month denominators.
- Separated service-date incurred reporting from payment-date cash-flow
  reporting and retained current-version claim scope.
- Defined year-over-year price, utilization, and service-mix effects with a
  $0.01 reconciliation tolerance.
- Defined top-ten share and HHI concentration measures plus robust historical
  surge thresholds.
- Prohibited M03 ground truth from ordinary metrics and required synthetic
  small-cell suppression for publication.

### Current work

Publishing the M06 contract and automated governance tests through issue #62.

### Next task

Generate and reconcile the five deterministic cost-intelligence outputs from
the trusted M04 model, then publish machine-readable quality evidence and
synthetic-only samples.

## 2026-08-04 — M06 cost-intelligence model generation

### Completed

- Generated all five M06 analytical tables without reading the anomaly bridge.
- Published 72 cost-utilization, 76 payment cash-flow, 144 concentration, 168
  decomposition, and 288 early-warning rows.
- Reconciled PMPM and utilization to active eligible member months while
  preserving separate service-date and payment-date outputs.
- Validated concentration bounds and $0.01 decomposition reconciliation.
- Published synthetic samples, stable hashes, deterministic Parquet bytes, and
  20 passing machine-readable quality checks.

### Current work

Publishing the M06 implementation and validation through issue #64.

### Next task

Complete M06 and begin M07 policy-impact analysis with governed treatment and
comparison cohorts plus pre-policy and post-policy diagnostics.

## 2026-08-04 — M07 policy-impact analysis contracts

### Completed

- Defined the balanced provider-month panel with twelve pre-policy and six
  post-policy months and frozen treatment/comparison assignments.
- Governed five outcomes with explicit numerator, denominator, and date roles.
- Specified two-way fixed-effects difference-in-differences with
  provider-clustered standard errors.
- Defined event-study, joint pre-trend, placebo-date, and sensitivity analyses.
- Defined typed coefficient, confidence-interval, diagnostic, and quality
  outputs while prohibiting anomaly ground truth from model inputs.

### Current work

Publishing the M07 statistical design and contracts through issue #67.

### Next task

Construct the provider-month panel, estimate policy effects, and publish
reproducible event-study and diagnostic evidence.

## 2026-08-05 — M07 policy-impact estimation and diagnostics

### Completed

- Constructed a balanced 3,600-row panel for 200 providers across 18 months.
- Estimated exposure-weighted two-way fixed-effects models for five outcomes
  with provider-clustered standard errors.
- Published 15 primary/sensitivity estimates, 85 event-study coefficients, and
  10 pre-trend/placebo diagnostics.
- All primary effects were statistically non-significant; all joint pre-trend
  and placebo tests passed at the configured 5% level.
- Retained unweighted PMPM direction reversals as an explicit exposure-weighting
  sensitivity and limitation rather than causal evidence.
- Preserved ground-truth isolation and deterministic typed output controls.

### Current work

Publishing the M07 analysis and diagnostic evidence through issue #69.

### Next task

Complete M07 and begin M08 independent SAS reconciliation of key financial,
utilization, rules-engine, and policy-analysis totals.

## 2026-08-05 — M08 SAS reconciliation contracts

### Completed

- Recorded that the local macOS environment has no SAS executable and set the
  execution status to `not_executed`.
- Defined twelve reconciliation metrics spanning trusted claims, membership,
  cost intelligence, payment integrity, and policy impact.
- Defined exact count, one-cent financial, rate, coefficient, and p-value
  tolerances plus portable UTF-8 CSV exchange rules.
- Defined ordered SAS programs, log-quality requirements, checksums, runtime
  evidence, and the machine-readable comparison-result schema.
- Prohibited simulated or Python-generated evidence from being represented as
  successful independent SAS validation.

### Current work

Publishing the M08 contract and execution-package design through issue #72.

### Next task

Generate portable synthetic reconciliation extracts and Python references,
implement the ordered SAS programs, then execute them in an authorized SAS
environment before closing M08.

## 2026-08-05 — M08 portable SAS reconciliation package

### Completed

- Exported six governed UTF-8 CSV inputs with deterministic SHA-256 manifests.
- Generated 181 Python reference comparisons covering all twelve metric IDs.
- Implemented seven ordered SAS programs using a configurable package root and
  no embedded local user paths.
- Implemented SAS log scanning for errors and unintended conversion warnings.
- Added clean-runner tests that rebuild all upstream analytical fixtures and
  verify repeated package hashes.
- Preserved `not_executed` status because no SAS runtime was used.

### Current work

Publishing portable package preparation through issue #74.

### Next task

Execute the package in SAS 9.4M7+ or SAS Viya 4, preserve the real versioned
log, compare all results, and close M08 only if governed tolerances pass.

## 2026-08-06 — M08 first independent SAS execution

### Completed

- Executed the package in SAS OnDemand for Academics using SAS 9.4 M8 on
  Linux, satisfying the governed runtime minimum.
- Confirmed all six inputs import and the result CSV and SAS dataset publish.
- Detected a real `comparison_scope` truncation warning while combining domain
  metric tables.
- Diagnosed 176 unmatched SAS values that were incorrectly marked passed
  because SAS numeric missing values compare below nonmissing tolerances.
- Updated publication logic to preserve 64-character scopes and require
  nonmissing reference values, SAS values, and tolerances before passing.
- Added the required execution identifier to every result row after the first
  real output exposed its absence from the portable publication program.
- Completed corrected execution `M08_20260806_FINAL` in SAS 9.4 M8 on Linux.
- Independently validated 181 result rows: 181 passed, zero failed, zero
  missing SAS values, and all SAS001-SAS012 reference keys matched.
- Published checksums for the input manifest, reference file, seven programs,
  real SAS log, and final result CSV in machine-readable quality evidence.
- Added `codex/**` to CI push branches after PR #76 produced no GitHub Actions
  run despite an active pull-request trigger.

### Current work

Publishing the corrected SAS programs, reproducible execution validator, and
checksum-backed M08 completion evidence.

### Next task

Merge the M08 completion evidence, close issue #71, and begin M09 Fabric and
Azure cloud demonstration planning.

## 2026-08-09 — M09 Fabric deployment contract

### Completed

- Verified university-tenant Fabric portal access with a Free license and an
  available but unactivated trial offer.
- Verified an active Azure for Students subscription without recording its
  identifier, tenant identifier, user email, or billing details.
- Defined deterministic workspace, Lakehouse, notebook, pipeline, schema, and
  deployment-order contracts across M04-M07 curated outputs.
- Preserved restricted evaluation-only ground truth and separate service-date
  and payment-date analytical surfaces.
- Defined exact count and key reconciliation, one-cent financial tolerance,
  SHA-256 manifests, execution evidence, screenshot redaction, and teardown.
- Required explicit approval, budgets, alerts, and final-cost verification
  before any paid Azure resource can be provisioned.

### Current work

Publishing the contract-only M09 cloud readiness controls through issue #78.

### Next task

After the contract is merged, activate the approved Fabric trial, build the
portable cloud deployment package, execute the notebook and pipeline, reconcile
all governed tables, capture redacted evidence, and pause or delete resources.

## 2026-08-10 — M09 portable Fabric deployment package

### Completed

- Packaged 26 governed M04-M07 Parquet tables into domain-specific OneLake
  landing paths without re-encoding source bytes.
- Published deterministic SHA-256 hashes, Arrow schemas, access classes,
  primary keys, date roles, row counts, distinct-key counts, and governed
  financial references.
- Added a schema-enabled Fabric PySpark notebook that materializes Delta tables
  and fails when cloud count, key, or financial comparisons do not reconcile.
- Added a deterministic pipeline template for the governed notebook refresh.
- Kept three ground-truth tables in the separate restricted `evaluation`
  schema and excluded them from ordinary analytical domains.
- Extended clean-runner fixtures through payment integrity, cost intelligence,
  and policy impact so the cloud package is validated from a fresh checkout.
- Preserved the unactivated Fabric trial and created no cloud resources.

### Current work

Publishing the portable package and validation artifacts through issue #80.

### Next task

Merge the local package, confirm the Fabric capacity region, activate the trial,
create the schema-enabled Lakehouse, and perform the real cloud execution.

## 2026-08-10 — M09 Fabric Lakehouse execution

### Completed

- Activated a Fabric Trial capacity in North Central US without creating a paid
  Azure resource.
- Created the `hcpi-portfolio-m09` workspace and schema-enabled
  `lh_hcpi_curated` Lakehouse.
- Uploaded the deterministic landing package and manifest while keeping full
  cloud extracts outside Git.
- Imported and attached `nb_hcpi_load_validate` to the Lakehouse.
- Corrected the portable landing root from an absolute OneLake path to the
  Fabric-relative `Files` path after the first run exposed a 400 path error.
- Successfully materialized 26 governed Delta tables across `trusted`,
  `payment_integrity`, `cost_intelligence`, `policy_impact`, and restricted
  `evaluation` schemas.
- Published 33 reconciliation results: 33 passed and zero failed.
- Created, validated, and successfully executed `pl_hcpi_curated_refresh`.
- Retained private run identifiers and full screenshots outside Git.
- Recorded zero paid-resource cost and retained the trial workspace for M10.

### Current work

Publishing sanitized M09 execution evidence and the portable path correction
through issue #80.

### Next task

Merge the execution evidence, close issues #80 and #77, build the M10 Looker
Studio dashboard and compact Power BI validation report, then remove or allow
expiry of trial assets.

## 2026-08-11 — M10 BI semantic and dashboard contract

### Completed

- Defined a governed cross-tool semantic contract for Looker Studio and Power
  BI using the reconciled M06, M07, and M09 analytical surfaces.
- Documented 14 metrics with explicit grains, formulas, formats, source tables,
  and service-date, payment-date, or policy-date roles.
- Prohibited ambiguous many-to-many relationships and bidirectional filtering.
- Fixed count tolerance at zero and financial tolerance at $0.01.
- Required eligible member months for PMPM and governed exposure denominators
  for utilization rates.
- Defined privacy suppression for breakdowns containing fewer than 11 distinct
  synthetic members.
- Excluded the restricted M03 evaluation schema from ordinary BI features.
- Specified all six Looker Studio pages and the independent Power BI executive
  KPI validation scope.
- Added machine-readable quality checks and focused contract tests without
  claiming that either dashboard has been built.

### Current work

Publishing the M10 semantic-model and dashboard contract through issue #84.

### Next task

Build deterministic dashboard extracts, create and validate the six Looker
Studio pages, reproduce selected executive KPIs in Power BI from Fabric, and
capture sanitized refresh and screenshot evidence.

## 2026-08-11 — M10 governed dashboard extracts

### Completed

- Built seven deterministic, tool-neutral CSV extracts covering all 14 M10
  metrics and the six contracted Looker Studio page domains.
- Reconciled counts exactly and governed financial measures within $0.01.
- Reproduced PMPM and utilization measures from eligible member-month
  denominators.
- Applied the 11-distinct-member privacy threshold to review-lead breakdowns.
- Preserved visible service-month and payment-month date roles.
- Kept evaluation ground truth outside every ordinary dashboard feature.
- Published bounded samples and a machine-readable quality report while
  keeping full extracts outside Git.
- Added deterministic-build, reconciliation, privacy, and date-role tests.

### Current work

Publishing the governed extract package through issue #86.

### Next task

Load the extracts into Looker Studio, build and validate all six pages, then
reproduce selected executive KPIs in Power BI and capture sanitized evidence.
