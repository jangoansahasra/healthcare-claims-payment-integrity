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

## Prepared package

Run `python -m src.reconciliation.build_sas_package` after all upstream
analytical outputs exist. It exports six CSV inputs, a SHA-256 manifest, and
181 Python references for SAS001-SAS012. The deterministic package remains in
ignored `data/generated/sas_reconciliation` storage.

All seven programs under `sas/programs` use the configurable `ROOT` parameter.
Preparation evidence remains `not_executed` until a real SAS run produces a
versioned log that passes the governed error and conversion-warning scan.
