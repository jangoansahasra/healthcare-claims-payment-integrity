/* M08 setup. Pass ROOT with -set ROOT /portable/package/path. */
%macro require_root;
  %if %superq(ROOT)= %then %do;
    %put ERROR: ROOT must identify the portable SAS reconciliation package.;
    %abort cancel;
  %end;
%mend;
%require_root;
%macro require_execution_id;
  %if %superq(EXECUTION_ID)= %then %do;
    %put ERROR: EXECUTION_ID must identify the real SAS execution.;
    %abort cancel;
  %end;
%mend;
%require_execution_id;
libname recon "&ROOT./result";
%let input_root=&ROOT./input;
%let reference_root=&ROOT./reference;
%let result_root=&ROOT./result;
