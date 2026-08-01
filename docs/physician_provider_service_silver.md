# CMS Physician Provider-Service Silver Model

## Purpose

This model provides typed, governed benchmarks for Original Medicare
professional services at rendering NPI, HCPCS code, facility/non-facility
category, and reporting-year grain.

It contains aggregated observed activity—not claim lines or improper-payment
labels. Real providers must remain separate from synthetic anomaly injection.

## Coverage and typing

All 58,673,513 Bronze rows from 2019–2024 are retained. NPIs and HCPCS codes
remain strings. Seven analytical measures are typed:

- `BIGINT`: beneficiaries and beneficiary-day services
- `DECIMAL(38,6)`: total services, submitted charge, allowed amount, Medicare
  payment, and standardized Medicare payment

Total services remains decimal because CMS service-count metrics vary by HCPCS.
The model preserves 55,901 fractional rows across 442 HCPCS codes.

## Publication and service semantics

Published provider-service combinations have at least 11 beneficiaries.
Unpublished combinations are not zero and are never reconstructed.

Beneficiary-day services remove same-day double counting for a beneficiary and
service. They are analytically distinct from total service units and remain a
separate measure.

## Payment semantics

Medicare payment must not exceed allowed amount; production has zero
violations. Submitted charge is not an expected-payment ceiling, so 101,936
allowed-above-charge and 10,104 payment-above-charge rows are retained.

Standardized payment removes geographic payment-rate differences and is not a
component of allowed payment. The 3,258,449 standardized-above-allowed rows are
therefore reported rather than rejected.

## Geography and longitudinal attributes

The model preserves explicit missing indicators for 6,134 state-FIPS rows and
41,175 RUCA-code rows. Peer state and RUCA are used only for U.S. providers;
foreign providers receive a `Not applicable` peer-geography value.

Provider attributes and HCPCS descriptions remain year-specific. This avoids
rewriting history for providers that move, change specialty, or update their
NPPES record and for HCPCS descriptions that change over time.

## Derived benchmark fields

Beneficiary-volume bands use pooled empirical quartiles:

- low: 11–17
- medium: 18–31
- high: 32–72
- very high: 73 or more

Recommended peer cohorts include HCPCS, place-of-service category, provider
type, country, U.S.-only state/RUCA, beneficiary-volume band, and reporting
year, with at least 11 peers.

## Quality results

- Bronze rows: 58,673,513
- Silver rows: 58,673,513
- duplicate or null business keys: 0
- invalid NPIs, HCPCS codes, or governed domains: 0
- fractional beneficiary and beneficiary-day counts: 0
- negative measures: 0
- Medicare-payment-above-allowed violations: 0
- foreign peer-geography violations: 0
- all 24 quality checks passed

The 1.7 GiB Silver Parquet remains excluded from Git. The contract, builder,
quality report, tests, and documentation are versioned.

## Reporting guardrails

- Benchmark deviation is not fraud or improper payment.
- HCPCS descriptions are consumer-friendly references, not clinical coding
  documentation.
- Facility-setting professional payment does not include the facility payment.
- Standardized payment supports comparison but is not an actual payment component.
- Public views must suppress small peer groups and exclude direct provider details.
