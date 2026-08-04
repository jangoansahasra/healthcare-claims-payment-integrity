# Healthcare Claims Payment Integrity & Cost Intelligence Platform

An end-to-end healthcare insurance analytics portfolio project that reconciles
medical and pharmacy claims, identifies potentially incorrect payments,
explains emerging cost drivers, and estimates the impact of a simulated
claims-review policy.

## Central business question

> Why did healthcare claims cost change, how much is potentially attributable
> to payment errors, and did the new review policy improve outcomes?

## Project principles

- Use only public-use or synthetic data.
- Treat every payment-integrity flag as a review lead, not proof of fraud.
- Preserve claim and transaction history rather than overwriting adjustments.
- Separate service-date, adjudication-date, and payment-date reporting.
- Make every flag explainable and traceable to a versioned rule.
- Run locally first and use Fabric/Azure for the final cloud demonstration.

## Planned architecture

| Layer | Local development | Cloud demonstration |
|---|---|---|
| Source | CMS SynPUF + generated data | ADLS/OneLake landing area |
| Storage | CSV and Parquet | OneLake/Lakehouse |
| Transformation | Python + DuckDB SQL | Fabric notebook/pipeline/warehouse |
| Validation | pytest + SQL + SAS | Fabric pipeline checks |
| Statistics | pandas, SciPy, statsmodels | Fabric notebook |
| BI | Power BI Desktop/web | Power BI semantic model |
| CI | GitHub Actions | GitHub Actions |

## Target deliverables

- Trusted dimensional claims model with documented grain
- Append-only payment/reversal/adjustment ledger
- Configurable and explainable payment-integrity rules
- Measured anomaly precision, recall, and dollars-at-risk performance
- Cost and utilization early-warning metrics
- Cost-change decomposition
- Difference-in-differences policy evaluation
- SAS/SQL/Python/Power BI reconciliation
- Six-page Power BI report and formal KPI dictionary
- Privacy, security, and data-quality controls

## Repository layout

```text
config/       Versioned rule and simulation configuration
data/         Local-only raw/processed data plus small publishable samples
docs/         Architecture, decisions, dictionary, governance, and KPIs
notebooks/    Statistical and exploratory analyses
powerbi/      DAX, theme, semantic-model notes, and final report
sas/          Independent SAS validation
sql/          DDL, transformations, rules, marts, and tests
src/          Python package
tests/        Automated tests
```

## Status

Repository governance, public-data ingestion, clean synthetic operational data
generation, and controlled synthetic anomaly injection are complete. The next
milestone builds the trusted claims layer.

## Safety and limitations

This project does not contain protected health information. Its audit rules are
synthetic analytical examples and are not production medical-payment policies,
clinical recommendations, or evidence of fraud, waste, or abuse.
