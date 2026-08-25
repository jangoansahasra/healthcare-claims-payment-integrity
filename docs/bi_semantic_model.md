# Governed BI semantic model

M10 publishes one governed metric contract to two presentation tools. Looker
Studio is the primary six-page portfolio dashboard. A compact Power BI report
independently reproduces four selected executive KPIs from the same governed
extract. DL-012 records that Power BI imports the governed `executive_kpi`
extract as an Excel workbook through OneDrive rather than connecting to the
Fabric Lakehouse SQL analytics endpoint directly, because the Fabric Trial
capacity expired before validation. Neither presentation layer owns business
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
investigation/methodology, and are built with sanitized evidence captured.
Power BI independently reproduces total allowed amount, total paid amount,
allowed PMPM, and paid PMPM from the governed extract with zero count
difference and financial differences within $0.01, and sanitized evidence has
been captured for both presentation tools.
