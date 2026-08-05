/* Trusted claims and membership: SAS001-SAS005. */
proc sql;
  create table work.claim_metrics as
  select "SAS001" as metric_id, "ALL" as comparison_scope,
         count(*) as sas_value from work.fact_claim
  union all
  select "SAS002", "ALL", count(distinct claim_key) from work.fact_claim
  union all
  select "SAS003", "ALL", sum(total_allowed_amount) from work.fact_claim
    where is_current_version=1 and claim_status="paid"
  union all
  select "SAS004", "ALL", sum(net_paid_amount) from work.fact_claim
    where is_current_version=1 and claim_status="paid"
  union all
  select "SAS005", "ALL", count(*) from work.fact_membership_month
    where coverage_status="active";
quit;
