# Test Strategy

## Purpose

Testing must demonstrate that the trusted claims model, payment-integrity
rules, financial reconciliations, statistical analyses, and dashboard metrics
are reproducible and internally consistent.

## Configuration tests

- YAML files parse successfully.
- Rule IDs are unique.
- Required project settings exist.
- Dates and thresholds are valid.
- Every enabled rule has severity and confidence metadata.

## Data-contract tests

- Required columns exist.
- Column types match the documented contract.
- Primary keys are unique and non-null.
- Foreign keys resolve.
- Categorical values belong to approved domains.
- Source file checksums match the source manifest.

## Claims data-quality tests

- Service dates follow valid chronology.
- Financial fields follow documented sign conventions.
- Header and line totals reconcile.
- Payments, reversals, and adjustments reconcile.
- Claim-version relationships are valid.
- Late adjustments are identified.
- Missing and invalid medical codes are measured.

## Payment-integrity tests

- Every enabled rule produces the standard flag schema.
- Every flag contains supporting evidence.
- Amount at risk is reproducible.
- Severity and priority values are valid.
- Injected anomalies are compared with ground truth.
- Precision, recall, false-positive rate, and dollars at risk are reported.

## Analytical tests

- PMPM denominators use eligible member months.
- Claims-per-1,000 measures use documented annualization.
- Cost decomposition reconciles to total observed change.
- Policy models report estimates and confidence intervals.
- Pre-policy trends are evaluated.
- Placebo specifications are evaluated.
- Provider-level clustering is used where appropriate.

## Cross-platform reconciliation

Key totals will be reproduced in:

- SQL
- Python
- SAS
- Power BI

Differences must be zero or explicitly attributable to documented rounding
behavior.

## Continuous integration

GitHub Actions will eventually run:

- Python linting
- Unit tests
- Configuration validation
- Small-data SQL tests
- Secret safeguards
- Oversized-file safeguards