# Synthetic Dimension and Eligibility Generation

## Purpose

The M02 dimension generator creates the clean population and relationship tables
required before synthetic claims can be produced. It uses only synthetic
identifiers and aggregate calibration labels.

Run the governed build with:

```bash
python -m src.synthetic.build_synthetic_dimensions
```

## Deterministic method

Each generated choice is derived from SHA-256 over the configured seed, a field
namespace, and an entity sequence number. The method does not depend on mutable
global random state. Stable sorting and contract-derived Arrow schemas produce
content-stable outputs for a fixed configuration and library version.

The committed quality report records canonical row-content SHA-256 hashes that
are independent of Parquet metadata.

## Generated tables

| Table | Rows | Description |
|---|---:|---|
| `member` | 10,000 | Synthetic birth year, sex, state, and synthetic marker |
| `plan` | 4 | Commercial and Medicare Advantage plan definitions |
| `provider` | 200 | Synthetic specialty, geography, entity type, and calibration lineage |
| `provider_contract` | 800 | Every synthetic provider contracted with each plan |
| `membership_month` | 158,746 | Active member-plan coverage by month |
| `policy_assignment` | 200 | Treated or comparison assignment by provider region |

The eligibility table spans all 18 reporting months. Individual members have at
least six months of coverage, with deterministic entry and early termination.

## Calibration and semantic controls

- Provider specialty groups retain only aggregate CMS source-family and period
  labels; no NPI, provider name, or address is copied.
- Inpatient and outpatient facility specialties are always organizations.
- Medicare Advantage members are at least 65 at the reporting-period start.
- Treated regions are Northeast and Midwest, as configured in `project.yml`.
- Treated and comparison cohorts are both required to be non-empty.
- Every member and provider row carries an explicit synthetic marker.

## Outputs

Full Zstandard Parquet files are written atomically under
`data/generated/synthetic/` and remain excluded from Git. Small, deterministic,
synthetic-only CSV samples are written under `data/sample/synthetic/` for public
inspection.

The machine-readable quality report is stored at
`data/metadata/quality/synthetic_dimensions_eligibility.json`.

## Quality controls

The build validates:

- configured row counts;
- contract column order and Arrow schemas;
- primary-key uniqueness and completeness;
- foreign-key relationships;
- synthetic identifier formats;
- eligibility, contract, and policy effective dates;
- age eligibility for plan assignment;
- facility-provider entity semantics;
- treated and comparison cohort presence;
- Parquet row counts and schemas;
- repeatable canonical content hashes.
