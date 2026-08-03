# Project Plan

## Objective

Build a cloud-based healthcare claims analytics platform that establishes a
trusted claims dataset, detects potentially incorrect payments, explains
emerging cost drivers, evaluates a simulated claims-review policy, and gives
auditors an explainable investigation queue.

## Central business question

> Why did healthcare costs change, how much is potentially attributable to
> payment errors, and did the claims-review policy improve outcomes?

## Status definitions

- Not started: Work has not begun.
- In progress: Implementation or validation is underway.
- Blocked: Work requires an unresolved dependency or decision.
- Complete: Deliverables are implemented, tested, and documented.

## Milestones

| ID | Milestone | Status | Exit criteria |
|---|---|---|---|
| M00 | Repository and governance | Complete | GitHub, tracking, CI, and contribution workflow established |
| M01 | Public-data ingestion | Complete | CMS datasets downloaded reproducibly and source metadata recorded |
| M02 | Synthetic operational data | Complete | All 14 governed operational tables generated and validated |
| M03 | Anomaly injection | In progress | Ten anomaly types injected with complete ground truth |
| M04 | Trusted claims model | Not started | Dimensional model built, tested, and reconciled |
| M05 | Payment-integrity engine | Not started | Explainable rules evaluated against ground truth |
| M06 | Cost intelligence | Not started | Cost, utilization, concentration, and early-warning metrics validated |
| M07 | Policy-impact analysis | Not started | Difference-in-differences estimate and diagnostics completed |
| M08 | SAS reconciliation | Not started | Key totals independently reproduced in SAS |
| M09 | Fabric and Azure | Not started | Curated data and pipelines demonstrated in the cloud |
| M10 | Power BI | Not started | Six report pages and documented semantic model completed |
| M11 | Portfolio delivery | Not started | README, results, screenshots, presentation, and demo completed |

## Success measures

| Measure | Target |
|---|---:|
| Injected-anomaly recall | At least 85% |
| Payment-integrity precision | At least 70% |
| False-positive rate | Below 10% |
| SQL/Python/SAS financial difference | $0.01 or less |
| Cost-attribution residual | Below 5% |
| Cost-surge detection delay | One monthly refresh or less |
| Displayed KPIs documented | 100% |
| Privacy-sensitive visuals tested | 100% |
| Portfolio pipeline refresh | Below 10 minutes |

## Working method

For every milestone:

1. Create or select a GitHub issue.
2. Create a feature branch from current `main`.
3. Implement one bounded change.
4. Run relevant tests.
5. Update documentation and the progress log.
6. Review the diff.
7. Commit and push.
8. Open a pull request.
9. Merge only after validation.
10. Close the corresponding issue.
