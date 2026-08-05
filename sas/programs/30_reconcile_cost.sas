/* Cost intelligence: SAS006-SAS007. */
data work.cost_metrics;
  set work.monthly_cost_utilization;
  length metric_id $6 comparison_scope $64;
  comparison_scope=cats(put(service_month,yymmdd10.),"|",plan_key);
  metric_id="SAS006"; sas_value=allowed_amount/eligible_member_months; output;
  metric_id="SAS007"; sas_value=service_units*1000/eligible_member_months; output;
  keep metric_id comparison_scope sas_value;
run;
