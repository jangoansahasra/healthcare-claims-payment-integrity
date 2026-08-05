/* Import governed UTF-8 CSV files using configurable package roots. */
%macro import_csv(name);
  proc import datafile="&input_root./&name..csv" out=work.&name
    dbms=csv replace;
    guessingrows=max;
    getnames=yes;
  run;
%mend;
%import_csv(fact_claim);
%import_csv(fact_membership_month);
%import_csv(monthly_cost_utilization);
%import_csv(rule_finding);
%import_csv(provider_month_policy_panel);
%import_csv(policy_effect_estimate);
proc import datafile="&reference_root./python_reference.csv"
  out=work.python_reference dbms=csv replace;
  guessingrows=max;
  getnames=yes;
run;
