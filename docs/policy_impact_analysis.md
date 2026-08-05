# Policy-Impact Analysis Contract

M07 evaluates the simulated provider claims-review policy using a balanced
provider-month panel. The policy begins on January 1, 2026, following twelve
pre-policy months and preceding six post-policy months.

The primary estimator is a two-way fixed-effects difference-in-differences
model. The treatment effect is the coefficient on treatment assignment
interacted with the post-policy indicator. Provider fixed effects control for
time-invariant provider differences; month fixed effects control for shared
monthly changes. Standard errors are clustered by provider.

Five governed outcomes are evaluated: paid PMPM, allowed PMPM, claims per
1,000 attributed member months, denial rate, and review rate. Service-date and
review-date ownership is explicit, and every rate retains its numerator and
denominator lineage.

An event study uses event month -1 as its omitted reference. Pretreatment
coefficients from -12 through -2 receive a joint Wald test. A July 2025 placebo
policy date and balanced-panel, 99% winsorized, and unweighted sensitivities
make limitations visible.

These estimates are synthetic analytical evidence. They demonstrate a sound
evaluation workflow but do not establish production causal effects. Controlled
anomaly ground truth is prohibited from model inputs. Full results remain
outside Git; only synthetic samples and quality evidence may be published.
