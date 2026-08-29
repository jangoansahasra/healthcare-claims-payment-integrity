# Portfolio Presentation Outline

## Audience

Recruiters, hiring managers, and technical interview panels.

## Purpose

Demonstrate end-to-end analytics engineering, healthcare claims domain knowledge, statistical discipline, cloud execution, governance, and business communication.

## Slide 1 — Title

Healthcare Claims Payment Integrity & Cost Intelligence Platform

Subtitle:
End-to-end analytics engineering with Python, SQL, SAS, Microsoft Fabric, Looker Studio, and Power BI

## Slide 2 — Business problem

- Explain why healthcare claims costs changed
- Identify payments that merit human review
- Evaluate whether a simulated review policy changed outcomes
- Preserve traceability, privacy, and reproducibility
- Avoid presenting review leads as fraud determinations

## Slide 3 — Platform architecture

Flow:

Public-use and synthetic data
→ Controlled anomaly injection
→ Trusted dimensional claims model
→ Payment-integrity and cost-intelligence analytics
→ Policy-impact evaluation
→ SAS and Fabric validation
→ Looker Studio and Power BI

Key controls:

- Versioned contracts
- Deterministic builds
- Automated tests
- Evaluation-ground-truth isolation
- Explicit service-date and payment-date roles

## Slide 4 — Payment-integrity performance

Headline:
Explainable review prioritization with strong controlled-test performance

Metrics:

- 10 explainable rules
- 500 synthetic evaluation labels
- 88% precision
- 88% recall
- 0.01% false-positive rate
- 99.46% exposure recall
- $14.83M detected expected exposure

Limitation:
Individual rule performance varies; every finding requires human review.

Suggested visual:
Payment-integrity dashboard screenshot.

## Slide 5 — Cost intelligence

Headline:
Separate care utilization from payment cash flow

Capabilities:

- Allowed and paid PMPM
- Claims and units per 1,000
- Provider and service concentration
- Price-utilization-mix decomposition
- Robust early-warning signals
- 20 passing quality checks
- One-cent decomposition reconciliation

Suggested visual:
Cost and utilization dashboard screenshot.

## Slide 6 — Simulated policy evaluation

Headline:
A statistically disciplined result can be “no demonstrated effect”

Evidence:

- 3,600 provider-month observations
- 200 providers
- Five evaluated outcomes
- No statistically significant primary estimate
- All pre-trend tests passed
- All placebo tests passed
- Exposure-weighting sensitivity retained as a limitation

Suggested visual:
Policy-impact dashboard screenshot.

## Slide 7 — Independent validation and cloud execution

SAS:

- 181 comparisons passed
- 0 failures
- 0 missing SAS values

Microsoft Fabric:

- 26 governed tables
- 23 ordinary and 3 restricted
- 33 reconciliation checks passed
- Notebook and pipeline succeeded
- $0 paid cloud-resource cost

## Slide 8 — Governed business intelligence

- Seven deterministic dashboard extracts
- Fourteen governed KPI definitions
- Six Looker Studio pages
- Four independently validated Power BI KPIs
- Zero count differences
- Financial reconciliation within $0.01
- Privacy suppression below 11 members
- Restricted ground truth excluded

Suggested visuals:
Executive Looker Studio screenshot and Power BI validation screenshot.

## Slide 9 — What this project demonstrates

- Analytics engineering
- Dimensional healthcare claims modeling
- Explainable payment-integrity rules
- Statistical policy evaluation
- Python, SQL, and SAS reconciliation
- Microsoft Fabric orchestration
- Looker Studio and Power BI
- Testing, privacy, governance, and documentation

Closing statement:

A reproducible analytics platform that explains cost changes, prioritizes review leads, evaluates policy effects honestly, and delivers governed results across multiple tools.