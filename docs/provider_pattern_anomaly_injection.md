# Provider Amount and Utilization Anomaly Injection

## Scope

This M03 stage composes the existing PI001–PI006 anomalous dataset and appends
50 PI007 provider amount outliers and 50 PI008 provider-period utilization
surges. The clean M02 files are read-only and verified against their 14-table
hash manifest before and after generation.

## PI007 provider amount outliers

Eligible claim lines are grouped by the billing provider's synthetic specialty
and the line's service-code system. Each selected peer group contains at least
11 baseline lines. The injected allowed amount is strictly greater than 1.25
times the baseline peer maximum.

The mutation preserves the line's allowed-to-charge ratio and recalculates its
member liability. Corresponding claim-header totals and the positive payment
transaction are updated so header-line and payment reconciliation remain
valid. Expected exposure is the increase in plan payment after member
liability.

## PI008 provider-period utilization surges

Targets are synthetic provider-months in the post-policy period. Each provider
has at least six pre-policy baseline months and at least 11 historical claims.
The generator copies complete positively paid lifecycle templates from the
same provider-month until the resulting claim count strictly exceeds three
times the provider's pre-policy monthly average.

Every inserted header, line, adjudication event, and payment transaction gets a
globally unique identifier and complete insertion lineage. Member-month
eligibility, provider-plan contracting, lifecycle dates, foreign keys, and all
financial reconciliation equations remain valid. Expected exposure is the sum
of inserted positive payments.

## Output and validation

The composed anomalous data and complete ground truth remain under the ignored
`data/generated/synthetic_anomalous/` tree. Git contains only two 25-row
synthetic demonstration samples and the machine-readable quality report.

The production build contains 400 total labels, 143,257 field-change rows, and
14 clean-baseline hash records. All 25 provider-pattern checks pass. PI007
exposure is $339,437.25 and PI008 exposure is $14,195,769.67.

## Governance

All targets, provider identities, members, and claims are synthetic. The peer
and historical thresholds create controlled evaluation truth; they are not
fraud findings or conclusions about any real provider. Public CMS records are
used only for aggregate calibration and are never anomaly targets.
