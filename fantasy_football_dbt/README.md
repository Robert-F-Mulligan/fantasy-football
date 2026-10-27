# Warehouse project

The project separates source-aligned staging, reusable intermediate transformations, contracted weekly marts and presentation views. Receiver metrics retain player/team/season/week grain, so traded players are not divided by an unrelated team's totals. All source plays remain visible to uniqueness tests; duplicates are not silently discarded.

## Run

Install `pip install -e ".[dbt,database]"` from the repository root. Configure DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD in the environment. No credentials belong in profiles.yml.

```powershell
$env:DBT_SCHEMA = 'ff_dev_yourname'
dbt build --project-dir fantasy_football_dbt --profiles-dir fantasy_football_dbt
dbt docs generate --project-dir fantasy_football_dbt --profiles-dir fantasy_football_dbt
```

DBT_SOURCE_SCHEMA defaults to `source`. Target schemas are always prefixed, for example `ff_dev_yourname_staging` and `ff_dev_yourname_marts`. This deliberately replaces the old macro that could make development overwrite shared schemas. Existing shared schemas are not migrated or dropped automatically.

`dbt build` checks source identifiers, play uniqueness, required columns, a weekly mart schema contract, player/week uniqueness, valid counts/shares, and reconciliation of total targets. Unused example starter models have been removed. Historical source tables do not have arbitrary wall-clock freshness failures: their intended season coverage should be checked by the ingestion job. In production, schedule ingestion and dbt together and publish successful model runs only after tests pass.

## Deployment / CI contract

Use a distinct DBT_SCHEMA per developer and per CI run. Run `dbt build` and `dbt docs generate`; retain manifest.json and run_results.json as CI artifacts. A failed data test must fail deployment. Grant the runtime role read access to raw sources and ownership only of its prefixed schemas. Avoid deploying a partial PR into the shared production prefix. Configure production schema names through DBT_SCHEMA rather than changing SQL.

Models are views except the small weekly fact table, which is rebuilt atomically by dbt. Incremental materialization is intentionally deferred until ingestion supports stable update semantics and late stat corrections; adding an incremental filter prematurely would miss corrected plays.

Verified locally against 48,251 live stored 2024 plays: five models built and 24 tests passed in the `ff_verify_20261023_*` schemas. These review schemas remain available; no source tables were overwritten.

Sources: https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview and https://docs.getdbt.com/best-practices/how-we-structure/6-mapping-folders-to-warehouse

## Automated correction validation

The database CI job uses PostgreSQL 16 with disposable source and target schemas. It checks replay-safe keyed ingestion, rebuilds marts after a stat correction, and asserts team-specific shares and exclusion rules. See [database ingestion semantics](../docs/DATABASE_INGESTION.md). Existing production source constraints are not modified by CI.
