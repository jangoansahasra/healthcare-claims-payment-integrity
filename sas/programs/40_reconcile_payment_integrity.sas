/* Payment-integrity findings and exposure: SAS008-SAS009. */
proc sql;
  create table work.payment_metrics as
  select "SAS008" as metric_id, rule_id as comparison_scope,
         count(*) as sas_value from work.rule_finding group by rule_id
  union all
  select "SAS009", rule_id, sum(amount_at_risk)
    from work.rule_finding group by rule_id;
quit;
