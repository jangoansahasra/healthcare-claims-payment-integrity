# Portfolio Results

## Executive summary

This project delivers an end-to-end, synthetic healthcare claims analytics platform spanning reproducible ingestion, claims modeling, payment-integrity review leads, cost intelligence, policy evaluation, independent reconciliation, Microsoft Fabric execution, and cross-tool business intelligence.

All healthcare records and evaluation labels are synthetic or public-use. Payment-integrity findings are investigation leads, not evidence of fraud or improper payment.

## Payment-integrity performance

The governed engine evaluated 10 explainable rules against 500 controlled synthetic labels and produced 500 review leads.

Overall evaluation results:

| Measure | Result |
|---|---:|
| Precision | 88.00% |
| Recall | 88.00% |
| False-positive rate | 0.01% |
| Exposure recall | 99.46% |
| True positives | 440 |
| False positives | 60 |
| False negatives | 60 |
| Detected expected exposure | $14,832,732.48 |
| Labeled expected exposure | $14,912,978.73 |

The overall precision and recall targets passed. Individual rule performance varies, so every lead remains explainable and subject to human review.

## Cost intelligence

The deterministic cost-intelligence layer separates service-month utilization from payment-month cash flow and publishes:

| Output | Rows |
|---|---:|
| Monthly cost and utilization | 72 |
| Payment cash flow | 76 |
| Provider/service concentration | 144 |
| Cost-change decomposition | 168 |
| Early-warning evaluation | 288 |

All 20 machine-readable quality checks pass. Cost-change price, utilization, and mix effects reconcile to total cost change within $0.01.

Early-warning signals require at least six months of history, at least 100 eligible member months, a robust z-score of at least 3.0, and an absolute relative change of at least 20%.

## Simulated policy evaluation

The policy-impact analysis evaluates a synthetic claims-review policy using a balanced panel of 3,600 provider-month observations across 200 providers.

The primary exposure-weighted difference-in-differences estimates are:

| Outcome | Estimate | p-value |
|---|---:|---:|
| Paid PMPM | 160.2456 | 0.5307 |
| Allowed PMPM | 188.7401 | 0.5404 |
| Claims per 1,000 | 8.5613 | 0.6092 |
| Denial rate | -0.0067 | 0.2528 |
| Review rate | 0.0010 | 0.8125 |

None of the five primary estimates is statistically significant. All five joint pre-trend tests and all five placebo-date tests pass at the 5% level.

Unweighted paid and allowed PMPM estimates reverse direction, demonstrating sensitivity to unequal provider exposure. The project therefore does not claim that the simulated policy caused an improvement.

## Independent SAS reconciliation

SAS independently reproduced the governed analytical references:

| Measure | Result |
|---|---:|
| Reference comparisons | 181 |
| SAS result comparisons | 181 |
| Passed comparisons | 181 |
| Failed comparisons | 0 |
| Missing SAS values | 0 |

All governed comparisons passed within their specified count and financial tolerances.

## Microsoft Fabric execution

The governed cloud package was executed successfully in Microsoft Fabric:

| Measure | Result |
|---|---:|
| Governed tables | 26 |
| Ordinary tables | 23 |
| Restricted tables | 3 |
| Reconciliation checks | 33 |
| Passed reconciliation checks | 33 |
| Failed reconciliation checks | 0 |
| Paid cloud-resource cost | $0.00 |

Both the validation notebook and orchestration pipeline completed successfully. Restricted evaluation tables remained separated from ordinary analytical features.

## Business-intelligence delivery

The presentation layer contains:

- Seven deterministic, tool-neutral dashboard extracts
- Fourteen governed KPI definitions
- Six Looker Studio dashboard pages
- One independent four-KPI Power BI validation report
- An 11-member privacy-suppression threshold
- Explicit service-month and payment-month ownership
- Evaluation-ground-truth exclusion
- Sanitized portfolio screenshots

Power BI independently reproduced total allowed amount, total paid amount, allowed PMPM, and paid PMPM from the governed executive extract. Count differences were zero and financial differences were within $0.01.

## Limitations

- Data and anomaly labels are synthetic or public-use.
- Review leads are not fraud determinations.
- Policy estimates demonstrate an evaluation workflow, not production causal effects.
- Early-warning signals are monitoring leads, not forecasts or clinical guidance.
- The rules and thresholds are analytical examples and require domain, legal, compliance, and operational review before production use.
