/* M08 setup. Pass ROOT with -set ROOT /portable/package/path. */
%macro require_root;
  %if %superq(ROOT)= %then %do;
    %put ERROR: ROOT must identify the portable SAS reconciliation package.;
    %abort cancel;
  %end;
%mend;
%require_root;
libname recon "&ROOT./result";
%let input_root=&ROOT./input;
%let reference_root=&ROOT./reference;
%let result_root=&ROOT./result;
