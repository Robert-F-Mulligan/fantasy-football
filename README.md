# Fantasy football research

Python tools for data ingestion, league-specific draft valuation, historical projection baselines, and interactive reports. The new workflow runs from CSV files without a database or live scraping.

See the [package map and import migration guide](docs/PACKAGE_LAYOUT.md) for the code layout and retained historical utilities.

## Quick start

Python 3.10+ is required. From the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[viz,dev,scraping,database,model]"
.\.venv\Scripts\python -m fantasyfootball draft examples/projections.csv --league examples/league.json --pick 5 --output work/draft.csv --html work/draft.html
.\.venv\Scripts\python -m fantasyfootball evaluate examples/history.csv --output work/evaluation.csv
.\.venv\Scripts\python -m pytest -q
```

The existing `ff-venv` environment can also run these commands. Examples contain **synthetic demonstration data**, not current player projections. Open the HTML report in a browser; Plotly is embedded for offline use. Hover, zoom, or click positions in the legend. Chart methods return figures for notebooks.

## Current data and league connection

Use `sync-data` for versioned nflverse downloads and `import-sleeper` for read-only league settings and rosters. See [data sources and import coverage](docs/DATA_SOURCES.md) for commands, identity reconciliation, and scoring limitations.

See [schedule-aware weekly planning](docs/WEEKLY_PLANNING.md) for live context snapshots, kickoff slot locks, injury flags, and offensive recommendations.

For a Wednesday email that runs with your PC off, see [hosted report setup](docs/HOSTED_REPORT.md).

## Draft inputs

Projections require `player_id`, `player_name`, `pos`, and `projected_points`. IDs must be stable, nonempty and unique. Supply every starting position and enough depth to include a player beyond each position's league-wide starter and flex demand. Missing depth raises an error rather than inventing replacement values.

If `projected_points` is absent, supply every stat configured in `ScoringRules`; the application computes league points. Missing stats are not assumed zero. FantasyPros transformer output is adapted automatically: plural touchdown/interception columns are normalized, and stats are rescored for your league. The provider's `projected_fantasy_points` total is retained for reference, not substituted for league-specific points. Optional `adp` and `adp_std` represent average draft pick and observed pick standard deviation. Alternatively use `--adp market.csv` to join by player ID. Missing market data remains unknown.

```powershell
python -m fantasyfootball draft projections.csv --league league.json --pick 17 --drafted player123 player456 --output work/board.csv --html work/board.html
```

The next pick defaults to your next snake-draft turn; override `--next-pick` for another format. Drafted players are removed after full-pool replacement values are calculated. This does not track your roster or optimize a full lineup.

Ranks sort by value over replacement, projected points, then ID. Replacement is the first player outside league-wide starting demand, allocating flex slots across eligible remaining players. Tiers split after an adjacent within-position projection drop exceeding 25 points (`GapTiers(gap=...)` in Python). Availability uses a normal ADP distribution conditional on the player still being available at the current pick. This is an **uncalibrated heuristic**, not a simulated draft.

## League rules

```json
{"teams":12,"starters":{"QB":1,"RB":2,"WR":2,"TE":1},"flex":1,"flex_positions":["RB","WR","TE"]}
```

Add `scoring` mapping stat columns to point weights. Defaults are full PPR, 4-point passing TDs and -2 interceptions. `LeagueSettings.from_legacy(config.sean)` preserves your existing league rules, including 6-point passing TDs. Precomputed projections must already match your league's scoring system.

```python
from fantasyfootball.core.domain import LeagueSettings
from fantasyfootball.drafting.application import DraftApplication
from fantasyfootball.legacy import config
league = LeagueSettings.from_legacy(config.sean)
board = DraftApplication(league).prepare(projections, pick=5, next_pick=20)
```

## Historical projections

History requires one row per `player_id, season`, plus `player_name`, `pos`, `games`, `fantasy_points`. Score all seasons with the same rules. `WeeklyHistoryAdapter(league.scoring)` converts PFR-style weekly rows to this schema. It requires regular-season data and explicit stat zeros, rejects duplicate weeks, and counts supplied weekly rows as games. Exclude inactive/non-game rows first.

```powershell
python -m fantasyfootball draft history.csv --season 2027 --adp market.csv --league league.json --output work/forecast.csv --html work/forecast.html
python -m fantasyfootball evaluate history.csv --output work/backtest.csv
```

`WeightedHistoryModel` weights the previous three seasons by recency, shrinks points per game toward a positional prior, and projects 17 games by default. Configure decay, prior strength, season length and lookback in Python. An optional `expected_games` column changes playing time. It does not infer retirements, transfers, injuries or rookies: filter eligible players and supplement new entrants with external projections.

`WalkForwardEvaluator` passes only earlier seasons to each forecast and reports MAE, RMSE and coverage on overlapping IDs. New entrants are excluded from errors, so coverage matters. Use held-out seasons and baseline comparisons before relying on a model; no accuracy advantage is claimed.

## Ingestion

```python
from fantasyfootball.facade.data_facade import DataFacade, load_config
facade = DataFacade(load_config())
print(facade.list_available_datasets())
data = facade.get_data('nflfastr_play_by_play', min_year=2023, max_year=2024)
facade.get_data('nflfastr_play_by_play', output_mode='csv', output_path='work/pbp.csv')
```

`df` is the default and returns a DataFrame. CSV and DB modes stream chunks and return `None`. Each CSV run replaces the file on its first successful chunk and appends subsequent chunks. Errors propagate; previously written chunks can remain. Database append is the default and repeat loads can duplicate rows. Explicit `if_exists='replace'` applies to the first chunk. Each DB chunk commits separately.

`load_config('config/data_config.json')` reads your edited local config; `load_config()` reads the packaged default. `fantasy-data --list` lists datasets. The ingestion CLI accepts `--config`, `--dataset_name`, and `--output-mode`. The facade's `request_delay` defaults to 5 seconds for PFR requests. Selenium uses Selenium Manager unless given a driver path. Live source HTML/blocking requires separate integration checks. PostgreSQL reads DB_HOST, DB_PORT, DB_NAME, DB_USER and DB_PASSWORD from the environment.

## Architecture

Frozen league/scoring objects hold configuration. `DraftApplication` orchestrates inputs and injected projection models. Separate strategies handle replacement, tiers and availability. Lazy factories load providers on demand. `BaseStrategy` owns ingestion lifecycle, cleanup and output. `PlotlyVisualizer` separates presentation from scraping and valuation.

See [migration notes](docs/MIGRATION.md). Older notebook modules remain for migration and require the `legacy` extra; the supported new entry points are the CLI and application service. DBT models and existing datasets are preserved.

Implementation references: [Plotly HTML export](https://plotly.com/python/interactive-html-export/) and [SQLAlchemy transactions](https://docs.sqlalchemy.org/en/20/core/connections.html).

## Factor models and weekly optimization

The new `forecast`, `evaluate-factors`, and `lineup` commands provide boosted-tree season/weekly forecasts and constrained lineup assignment. Install `pip install -e ".[model]"`. See [model features, usage and limitations](docs/MODELS.md), [live verification results](docs/VALIDATION.md), and [warehouse workflow](fantasy_football_dbt/README.md).

Run `python examples/verify_live.py` for bounded live checks. FantasyPros public projections expose a limited preview, not a complete draft pool. The scraper supports its current published JSON report payload without executing JavaScript. PFR may deny access with HTTP 403; no bypass is implemented. nflverse provides a verified alternative for play-by-play data.

## Maintenance and next steps

See the [repository audit and prioritized roadmap](docs/ROADMAP.md) for completed cleanup, retained legacy research, known data/model gaps, and the next draft and weekly-planning features.

Role-change research: [protocol and results](docs/ROLE_EXPERIMENT_RESULTS.md). The candidate remains experimental; production forecasts are unchanged.
