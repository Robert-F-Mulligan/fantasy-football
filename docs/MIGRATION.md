# Refactor and migration notes

## Behavior changes

- Facade and strategy calls default to `df`, not `db`.
- `data_facade.py` is canonical; the old misspelled `data_faceade.py` re-exports it.
- `list_available_datasets()` returns names; the CLI prints them.
- Exhausted retries and source failures raise instead of returning false success.
- CSV output keeps every year and chunk. Each in-memory run resets its state.
- Registries load lazily; plugins use factory `register` decorators. Importing a package no longer eagerly populates all registries.
- SQL writes commit, append operations are not retried, and connections are created only for DB output and disposed after use.
- The legacy draft script no longer scrapes on import. Use `DraftApplication` for offline research.
- Packaging includes every subpackage and default config. Metadata and optional dependencies are maintained in pyproject.toml.

## Extension points

Implement `predict(history, season)` to replace the projection baseline. Return unique player IDs, names, positions and projected points. Only earlier seasons should influence predictions. Evaluate new models against held-out years and compare with the baseline.

Implement `baselines(projections, league)` for replacement policies, `assign(board)` for tiers, or `probability(adp, std, pick, current_pick)` for availability, then inject into `DraftService`. Keep probability calibration separate from player scoring.

For providers, register components and implement `iter_frames(connector, sleep=...)`, yielding DataFrames and raising on failure. The shared lifecycle owns cleanup and output handling. Resolve stable player IDs explicitly before combining provider datasets; display names are not unique identifiers.

## Validation and scope

Offline tests cover ingestion lifecycle, year/chunk retention, retry exhaustion, DB commit behavior, transforms, scoring, flex demand, invalid inputs, future-data exclusion, ADP conditioning, CLI output and HTML escaping. Live provider HTML and PostgreSQL need integration checks in the target environment. DBT SQL, archived notebooks and old static-chart functions are retained.

Examples are synthetic. The historical baseline and normal-ADP heuristic do not claim predictive superiority. They establish replaceable, measurable models for future injury features, rookie estimates and opponent-draft models.
