# Package organization

The package root contains only `__init__.py`, `__main__.py`, and `cli.py`. Add new code to the package that owns its responsibility, rather than creating another root module.

| Package | Responsibility |
| --- | --- |
| `core` | League settings, scoring rules, shared validation |
| `data` | Player identities, source adapters, data snapshots, Sleeper imports |
| `forecasting` | Production features, predictive models, baselines, uncertainty |
| `drafting` | Draft application and player valuation |
| `lineups` | Weekly planning, eligible slots, lineup optimization |
| `reports` | Email rendering/delivery, hosted runner, interactive charts |
| `archives` | Forecast evidence capture and private GitHub persistence |
| `evaluation` | Accuracy scorecards and retrospective lineup evaluation |
| `experiments` | Candidate features and controlled backtests; not production defaults |
| `legacy` | Historical notebook helpers retained for reproducibility |

The existing `connectors`, `datasources`, `parsers`, `transformers`, `strategies`, `factories`, and `facade` packages implement the ingestion pipeline. `utils` contains its shared helpers. `data_config.json` remains a package resource.

## Import migration

The `fantasy-football`, `fantasy-data`, and `python -m fantasyfootball` entry points are unchanged. Direct Python imports and specialized module commands use the paths below. External notebooks and scripts must update their imports; no root forwarding modules are retained.

| Previous module | New module |
| --- | --- |
| `fantasyfootball.adapters` | `fantasyfootball.data.adapters` |
| `fantasyfootball.application` | `fantasyfootball.drafting.application` |
| `fantasyfootball.config` | `fantasyfootball.legacy.config` |
| `fantasyfootball.data_sync` | `fantasyfootball.data.data_sync` |
| `fantasyfootball.domain` | `fantasyfootball.core.domain` |
| `fantasyfootball.draft` | `fantasyfootball.legacy.draft` |
| `fantasyfootball.drafting` | `fantasyfootball.drafting.drafting` |
| `fantasyfootball.evidence` | `fantasyfootball.archives.evidence` |
| `fantasyfootball.fantasypros` | `fantasyfootball.legacy.fantasypros` |
| `fantasyfootball.features` | `fantasyfootball.forecasting.features` |
| `fantasyfootball.ffcalculator` | `fantasyfootball.legacy.ffcalculator` |
| `fantasyfootball.hosted` | `fantasyfootball.reports.hosted` |
| `fantasyfootball.models` | `fantasyfootball.forecasting.models` |
| `fantasyfootball.nflfastr` | `fantasyfootball.legacy.nflfastr` |
| `fantasyfootball.nflstats` | `fantasyfootball.legacy.nflstats` |
| `fantasyfootball.nflteamh2h` | `fantasyfootball.legacy.nflteamh2h` |
| `fantasyfootball.opportunity_experiment` | `fantasyfootball.experiments.opportunity_experiment` |
| `fantasyfootball.opportunity_features` | `fantasyfootball.experiments.opportunity_features` |
| `fantasyfootball.optimization` | `fantasyfootball.lineups.optimization` |
| `fantasyfootball.pfradv` | `fantasyfootball.legacy.pfradv` |
| `fantasyfootball.private_archive` | `fantasyfootball.archives.private_archive` |
| `fantasyfootball.projections` | `fantasyfootball.forecasting.projections` |
| `fantasyfootball.registry` | `fantasyfootball.data.registry` |
| `fantasyfootball.reporting` | `fantasyfootball.reports.reporting` |
| `fantasyfootball.scorecard` | `fantasyfootball.evaluation.scorecard` |
| `fantasyfootball.scorecard_archive` | `fantasyfootball.evaluation.scorecard_archive` |
| `fantasyfootball.sleeper` | `fantasyfootball.data.sleeper` |
| `fantasyfootball.specialists` | `fantasyfootball.forecasting.specialists` |
| `fantasyfootball.tiers` | `fantasyfootball.legacy.tiers` |
| `fantasyfootball.tiersweekly` | `fantasyfootball.legacy.tiersweekly` |
| `fantasyfootball.uncertainty` | `fantasyfootball.forecasting.uncertainty` |
| `fantasyfootball.usage_experiment` | `fantasyfootball.experiments.usage_experiment` |
| `fantasyfootball.usage_features` | `fantasyfootball.experiments.usage_features` |
| `fantasyfootball.visualization` | `fantasyfootball.reports.visualization` |
| `fantasyfootball.weekly` | `fantasyfootball.lineups.weekly` |

## Historical material

Tracked notebook source imports have been updated without changing saved outputs or metadata. This is an import migration, not a claim that all historical notebooks execute against current providers. The legacy utilities still have old optional dependencies and provider assumptions; `legacy/pfradv.py` references the already-missing `pfrgbg` module. They are not used by the hosted report.

Historical data, figures, notebooks, and experiment result manifests are retained. Old manifests describe the source layout at their original commit and must not be rewritten. Generated local environments, caches, credentials, and work files remain ignored rather than being included in the package.

Keep production forecasting independent of `legacy` and `experiments`. Hosted reporting orchestrates data, forecasting, lineup planning, and delivery; it must not make experimental features production defaults implicitly.

Research transforms share `research.inputs.ResearchWindow`, binary-flag validation, and team normalization. This keeps period/key contracts aligned without coupling descriptive research to the forecasting models.
