# Cost Intelligence Contract

## Purpose

M06 explains changes in synthetic healthcare cost and utilization from the
trusted M04 dimensional model. The layer is descriptive and operational: it
does not use controlled anomaly labels to construct ordinary metrics and does
not convert payment-integrity review leads into fraud conclusions.

The machine-readable source of truth is
`config/cost_intelligence_contract.yml`.

## Date roles

Service-month outputs use the current claim version's service date. Cash-flow
outputs use the append-only payment transaction date. These views answer
different questions and are never silently combined:

- Service month: when care occurred and eligible exposure existed.
- Payment month: when plan cash moved, including reversals and adjustments.

## Core rates

Eligible member months come from active `fact_membership_month` rows at member,
plan, and coverage-month grain. For a service month and plan:

- Allowed PMPM = allowed amount / eligible member months.
- Paid PMPM = net paid amount / eligible member months.
- Claims per 1,000 = distinct logical claims × 1,000 / eligible member months.
- Units per 1,000 = service units × 1,000 / eligible member months.
- Allowed per claim = allowed amount / paid claim count.

Only current claim versions contribute. Paid financial metrics use paid claims;
ordinary denied claims remain visible in claim counts but cannot create paid
cost.

## Concentration

Provider and service concentration are measured independently using allowed
amount. Each monthly plan population publishes its top-ten share and
Herfindahl-Hirschman Index (HHI). Both measures are bounded from zero to one;
higher values indicate greater concentration, not improper behavior.

## Cost-change decomposition

Year-over-year comparisons use the same calendar month from the prior year.
At plan and service-category grain, total allowed-cost change is divided into:

- price effect: change in allowed amount per unit at base utilization;
- utilization effect: change in units at the base unit price; and
- mix effect: the remaining service-category composition change.

The three effects must equal total cost change within $0.01. Zero-unit cells
produce null unit prices instead of artificial zeros or imputed values.

## Early warning

Monthly PMPM and utilization signals compare the current value with up to 12
prior months, excluding the current month. A signal requires at least six
history months, at least 100 eligible member months, a robust z-score of 3.0 or
more, and an absolute relative change of at least 20%. Median and median
absolute deviation reduce sensitivity to isolated historical extremes.

Signals are explainable monitoring leads. They are not forecasts, clinical
guidance, payment policy, or fraud determinations.

## Publication controls

Full Parquet outputs remain under `data/curated/cost_intelligence` and outside
Git. Publishable samples must be synthetic and cells with fewer than 11 members
are suppressed. M03 ground truth is prohibited from ordinary metric inputs.
