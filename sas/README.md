# SAS Reconciliation Package

M08 independently reconciles selected portfolio results in SAS. The current
Mac does not have a SAS runtime: `command -v sas` returned no executable and
`sas -version` returned `command not found` on 2026-08-05. Therefore the
current status is **not executed**, not passed.

The machine-readable contract is `config/sas_reconciliation_contract.yml`.
Generated UTF-8 CSV inputs, Python references, and SAS results belong under
`data/generated/sas_reconciliation` and remain outside Git.

## Required execution order

Run `00_setup.sas`, `10_import_inputs.sas`, the four domain reconciliation
programs in numeric order, and `90_publish_results.sas`. Execution requires SAS
9.4M7 or later or SAS Viya 4. Preserve the complete log, runtime version,
environment, program checksums, and input-manifest checksum.

M08 may be marked passed only when a real SAS log contains zero errors, no
unintended type-conversion warnings, and every comparison is within its
governed tolerance. Python, DuckDB, or mocked output cannot substitute for SAS
execution evidence.
