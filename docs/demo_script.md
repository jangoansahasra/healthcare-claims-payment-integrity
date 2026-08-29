# Portfolio Demo Script

## Purpose

This five-minute walkthrough presents the healthcare claims payment-integrity platform to recruiters, hiring managers, and technical interviewers.

## 1. Business problem — 30 seconds

Healthcare claims organizations need to understand why costs changed, identify payments that merit review, and determine whether operational policies improved outcomes.

This project addresses those questions using a governed analytics platform built entirely from synthetic and public-use data. Review leads are treated as investigation candidates, never as proof of fraud.

## 2. Architecture — 45 seconds

The platform follows a layered architecture:

1. Reproducible public-data ingestion and synthetic operational-data generation
2. Controlled anomaly injection with isolated evaluation ground truth
3. Trusted dimensional claims and append-only payment models
4. Explainable payment-integrity rules
5. Cost, utilization, concentration, and early-warning analytics
6. Difference-in-differences policy evaluation
7. Independent SAS reconciliation
8. Microsoft Fabric cloud execution
9. Looker Studio dashboards with Power BI KPI validation

Each layer has versioned contracts, deterministic builds, automated tests, reconciliation evidence, and privacy controls.

## 3. Payment-integrity results — 60 seconds

The engine evaluates 10 explainable rules against 500 controlled synthetic labels.

Overall performance reached 88% precision and 88% recall, with a 0.01% false-positive rate. Exposure recall reached 99.46%, capturing approximately $14.83 million of $14.91 million in labeled expected exposure.

Individual rule performance varies, which is intentionally visible. The system produces a prioritized and explainable human-review queue rather than automated fraud conclusions.

## 4. Cost intelligence and monitoring — 45 seconds

The cost-intelligence layer keeps service-month utilization separate from payment-month cash flow.

It calculates allowed and paid PMPM, claims and units per 1,000 member months, provider and service concentration, and price-utilization-mix decomposition.

All 20 quality checks pass, and decomposition components reconcile to total cost change within one cent. Early-warning signals use minimum history, exposure, robust z-score, and relative-change requirements to prevent weak signals from being presented as alerts.

## 5. Policy evaluation — 45 seconds

The project evaluates a simulated provider claims-review policy using a balanced panel of 3,600 provider-month observations across 200 providers.

None of the five primary outcomes is statistically significant. All pre-trend and placebo checks pass, but sensitivity analysis shows that exposure weighting affects some estimates.

The correct conclusion is therefore not that the policy worked. The result demonstrates a transparent evaluation workflow and communicates uncertainty honestly.

## 6. Independent validation and cloud execution — 45 seconds

SAS independently reproduced all 181 governed comparisons with zero failures and no missing SAS values.

The Microsoft Fabric implementation successfully loaded 26 governed tables—23 ordinary and three restricted—and passed all 33 cloud reconciliation checks. Both the notebook and pipeline completed successfully, with no paid cloud-resource cost.

## 7. Dashboards — 45 seconds

The presentation layer uses seven deterministic extracts and 14 governed KPI definitions.

Looker Studio provides six pages covering executive KPIs, cost and utilization, concentration, payment-integrity review leads, policy impact, and methodology signals.

Power BI independently reproduces four executive KPIs. Counts match exactly, and financial values reconcile within one cent.

Privacy-sensitive breakdowns require at least 11 distinct synthetic members, and restricted evaluation ground truth is excluded from ordinary dashboard features.

## 8. Closing — 30 seconds

This project demonstrates end-to-end analytics engineering rather than a standalone dashboard.

It combines data modeling, explainable rules, statistical analysis, SAS validation, cloud execution, business intelligence, automated testing, privacy governance, and evidence-based communication.

The key outcome is a reproducible platform that explains cost changes, prioritizes payment-review leads, evaluates policy effects without overstating causality, and presents governed results across multiple BI tools.