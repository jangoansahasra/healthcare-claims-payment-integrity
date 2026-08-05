# Payment-Integrity Engine and Evaluation Contract

## Purpose

M05 turns the ten governed PI001–PI010 scenarios into a reproducible,
explainable rules-engine evaluation. Each rule produces review leads with
supporting evidence and a reproducible amount at risk. Findings are not fraud
determinations.

The versioned machine-readable contract is
`config/payment_integrity_contract.yml`. The reference implementation executes
the rules and publishes deterministic findings and evaluation evidence.

## Detection and evaluation boundary

Detection reads trusted dimensions and facts but cannot read
`bridge_claim_anomaly`. Findings and their content hashes are frozen before a
separate evaluator opens the ground-truth bridge. This prevents the expected
labels or exposure amounts from influencing target selection, rule thresholds,
confidence, explanations, or dollars at risk.

The evaluator performs exact matching on three elements:

1. rule ID;
2. label scope; and
3. the canonical target identity for that scope.

Claim, claim-line, payment-transaction, provider, and provider-period labels
have separate canonical identities. A multi-label target is evaluated once per
rule, so overlapping labels remain distinguishable rather than collapsing into
one generic anomaly.

## Contracted outputs

| Table | Grain | Purpose |
|---|---|---|
| `rule_run` | One row per engine execution | Records input variant, seed, status, finding count, and leakage controls |
| `rule_finding` | One row per run, rule, scope, and canonical target | Standard explainable review lead with severity, confidence, and amount at risk |
| `finding_evidence` | One row per finding and evidence sequence | Preserves observed values, comparisons, thresholds, and source lineage |
| `finding_ground_truth_match` | One row per finding or injection evaluation result | Audits true-positive, false-positive, and false-negative matching |
| `rule_evaluation` | One row per run and rule or overall scope | Publishes confusion counts, rates, exposure recall, and threshold outcomes; overall rows use `ALL` as the rule ID |

Full Parquet outputs are written under `data/curated/payment_integrity` and are
excluded from Git. Only small synthetic samples and machine-readable quality
evidence may be committed.

The governed review capacity is capped at the top 50 findings per rule, ranked
by each rule's reproducible signal strength and then target identifier. Signal
strength is derived from ordinary evidence such as identifier sequence,
threshold ratio, excess frequency, or amount at risk—not from ground truth.
This models a finite audit queue and prevents rules with broad eligible
populations from crowding out other scenarios.

## Measured evaluation

The governed run produced 500 findings against 500 controlled labels:

- true positives: 440;
- false positives: 60;
- false negatives: 60;
- precision: 88.0%;
- recall: 88.0%; and
- false-positive rate: 0.01% after four-decimal reporting.

PI002–PI006, PI008, and PI009 reached 100% precision and recall. PI001 reached
92%, PI007 reached 86%, and PI010 reached 2%. The PI010 result is intentionally
retained as a limitation: the small compatibility mapping also matches many
ordinary synthetic claims, so clinical compatibility needs richer context
before any production-like use. Overall portfolio targets pass, but per-rule
results must not be hidden behind the aggregate.

## Metrics

- Precision = true positives / (true positives + false positives)
- Recall = true positives / (true positives + false negatives)
- False-positive rate = false positives / (false positives + true negatives)
- Exposure recall = detected expected exposure / labeled expected exposure

The portfolio targets are at least 70% precision, at least 85% recall, and
less than 10% false-positive rate. A zero denominator returns null rather than
an invented perfect or zero score. Counts and metrics are reported per rule
and overall.

## Governance

All targets and identities are synthetic. Rules are controlled analytical
examples, not production coverage policy, clinical advice, findings against
real providers, or proof of fraud. M03 ground truth remains evaluation-only and
is prohibited from ordinary rules-engine inputs.
