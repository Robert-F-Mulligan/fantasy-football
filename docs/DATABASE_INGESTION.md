# Repeatable database imports

Use `SqlConnector.publish(frame, table_name, if_exists="upsert", unique_keys=["game_id", "play_id"], schema="source")` for corrected play snapshots. Strategies accept the same `if_exists` and `unique_keys` configuration; every frame retains upsert mode. Existing callers continue to append unless they opt in.

Provision the table and a primary key or full unique constraint first. For play-by-play the identity is `(game_id, play_id)`. Inspect and reconcile duplicates before adding a constraint to an existing source table; the connector does not delete duplicates or migrate live tables automatically. Other datasets must choose their own documented grain rather than reuse play identifiers.

Each DataFrame is one transaction, including all its chunks. Replays update matching rows; corrections replace only supplied non-key columns, and rows absent from the batch remain. Nulls explicitly supplied in non-key columns replace prior values. Omitted columns retain prior values on updates, but inserts still require every non-null column without a default. A keys-only frame uses conflict-do-nothing and has the same insert constraints. Null or duplicate input keys, missing columns and mismatched destination keys fail. PostgreSQL and SQLite are supported; other dialects fail explicitly.

A multi-frame import is not one transaction: earlier successful frames remain if a later frame fails. A replay can resume safely with stable keys. Across frames, the last correction wins; callers must order revisions and must not replay older snapshots over newer corrections. Upsert does not infer revision timestamps, remove deleted source plays, or provide historical versioning. The ingestion timestamp (`created_at` in legacy strategies) is refreshed on correction; it is not an immutable creation timestamp.

## Validation

CI provisions an isolated PostgreSQL 16 service, runs the same connector contract tests as SQLite, then executes `python scripts/verify_database_ci.py`. The script builds a synthetic play source in uniquely named schemas, builds/tests dbt, applies a stat correction, rebuilds/tests dbt, checks exact mart values and generates docs. It drops only schemas created by that invocation. It does not touch production source/target schemas. Local execution requires DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD and a `dbt` executable on PATH; `pip install -e ".[dev,database,dbt]"` supplies the dependencies.

Set TEST_DATABASE_URL to a disposable PostgreSQL database to run `pytest tests/test_sql_upsert.py`. Without it the PostgreSQL cases skip; SQLite cases still run. This checks real PostgreSQL behavior in CI rather than treating SQLite as equivalent.
