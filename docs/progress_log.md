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
