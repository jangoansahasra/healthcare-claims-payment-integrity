/* Policy panel and published primary estimates: SAS010-SAS012. */
proc sql;
  create table work.policy_metrics as
  select "SAS010" as metric_id, treatment_group as comparison_scope,
         count(*) as sas_value from work.provider_month_policy_panel
    group by treatment_group
  union all
  select "SAS011", outcome_name, coefficient from work.policy_effect_estimate
    where specification="balanced_panel"
  union all
  select "SAS012", outcome_name, p_value from work.policy_effect_estimate
    where specification="balanced_panel";
quit;
