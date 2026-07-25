# Architecture

## Logical flow

```text
CMS public-use files          Synthetic operational tables
          \                    /
           v                  v
             Raw / Bronze layer
                      |
             standardized schemas
                      v
             Trusted / Silver layer
        claims + membership + transaction ledger
                      |
       +--------------+----------------+
       |              |                |
       v              v                v
 Payment integrity  Cost marts   Policy-analysis panel
       |              |                |
       +--------------+----------------+
                      v
          Power BI semantic model
```

## Local-to-cloud parity

The repository treats SQL, Parquet, and configuration files as the portable
contract. Local development uses DuckDB and Python. The final demonstration
loads the same curated Parquet files into OneLake and implements warehouse
views or a Fabric Lakehouse SQL endpoint over them.

This approach retains genuine Fabric components while preventing cloud
capacity, storage, or orchestration services from being used during ordinary
development.

## Security boundary

- Only synthetic or CMS public-use records are processed.
- Secrets are never committed.
- Cloud credentials use Microsoft Entra identities.
- Any application secrets are stored in Key Vault only during the cloud demo.
- Public screenshots apply the configured minimum-cohort rule.
- Audit exports use synthetic identifiers and exclude unnecessary member data.
