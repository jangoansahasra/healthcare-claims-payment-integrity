/* Compare SAS values to Python references; status is based on real SAS output. */
data work.sas_metrics;
  set work.claim_metrics work.cost_metrics work.payment_metrics
      work.policy_metrics;
run;
proc sql;
  create table recon.sas_reconciliation_result as
  select r.*, s.sas_value, abs(r.python_value-s.sas_value) as absolute_difference,
         calculated absolute_difference <= r.tolerance as passed
  from work.python_reference r left join work.sas_metrics s
    on r.metric_id=s.metric_id and r.comparison_scope=s.comparison_scope;
quit;
proc export data=recon.sas_reconciliation_result
  outfile="&result_root./sas_reconciliation_result.csv" dbms=csv replace;
run;
