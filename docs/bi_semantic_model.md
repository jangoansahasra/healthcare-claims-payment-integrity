# Governed BI semantic model

M10 publishes one governed metric contract to two presentation tools. Looker
Studio is the primary six-page portfolio dashboard. A compact Power BI report
connects to the Fabric Lakehouse SQL analytics endpoint and independently
reproduces selected executive KPIs. Neither presentation layer owns business
logic.

The model consumes M09 tables in the `trusted`, `payment_integrity`,
`cost_intelligence`, and `policy_impact` schemas. The `evaluation` schema is
restricted from ordinary dashboard features. Relationships use explicit
many-to-one cardinality and single filter direction; ambiguous many-to-many
paths are prohibited.

Metric identifiers, sources, grains, formulas, formats, and date roles live in
`config/bi_semantic_contract.yml`. Financial comparisons allow a maximum
difference of $0.01; counts must match exactly. PMPM and per-1,000 measures use
eligible member months. Service-month measures remain visibly distinct from
payment-month cash flow.

Provider, service, plan, and investigation breakdowns suppress groups with
fewer than 11 distinct synthetic members. All records are synthetic. Findings
are review leads and policy estimates are synthetic analytical evidence, not
fraud determinations, clinical guidance, production policy, or causal proof.

The deterministic extract builder publishes seven tool-neutral CSV surfaces:
executive KPIs, cost and utilization, payment cash flow, privacy-governed
payment-integrity review leads, provider/service concentration, policy impact,
and methodology signals. Full extracts remain under `data/generated/bi` and
outside Git; only bounded samples and a machine-readable quality report are
published.

The six Looker Studio pages cover executive overview, cost and utilization,
payment-integrity review leads, concentration, simulated policy impact, and
investigation/methodology. Power BI independently validates selected Fabric
KPIs. Extract preparation is complete, but neither dashboard is claimed as
complete until the presentation tools are built and sanitized evidence is
captured.
