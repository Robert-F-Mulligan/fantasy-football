# Validation results

Validated with Python 3.12.8, pandas 2.2.3 and Plotly 6.9.0.

- 48 offline tests passed (including causal feature tests and constrained lineup assignment).
- Editable installation and wheel build succeeded.
- CLI generated a 240-player synthetic draft board and self-contained HTML report.
- Walk-forward evaluation ran against repository weekly data from 2019 through 2023 using config.sean scoring.

| Holdout season | Matched players | Coverage | MAE (season points) | RMSE |
|---|---:|---:|---:|---:|
| 2020 | 209 | 70.85% | 65.63 | 87.03 |
| 2021 | 224 | 75.93% | 66.11 | 85.51 |
| 2022 | 228 | 79.72% | 70.38 | 90.91 |
| 2023 | 219 | 74.24% | 68.86 | 90.69 |

Reproduce from the repository root with `python examples/backtest_local_history.py` after installation. Outputs go to work/local_history.csv and work/local_backtest.csv. The existing weekly files had no duplicate player-season-week rows or missing configured scoring cells in these years.

The baseline assumes 17 projected games even for the 2020 holdout, which had a 16-game schedule. It also does not predict missed games, rookies, retirements or team changes. Coverage excludes players absent from the forecast pool. These figures establish a starting point, not evidence of superior drafting performance.

## Live verification (October 24, 2026)

PostgreSQL 17.2: connected using process environment credentials; temporary-table write/read/rollback passed. Source data was not modified. The dbt project built five models and passed 24 tests against 48,251 stored 2024 plays in isolated ff_verify_20261023_* schemas. Documentation catalog generation passed.

FantasyPros: public projections parsed for QB/RB/WR/TE (40 total rows, including nonzero reception projections). The provider exposes only ten public rows per position; this is not sufficient for a complete draft board. Public report parsing replaces the now-absent HTML table. PFR returned HTTP 403 and remains blocked; no bypass was attempted. nflverse returned a valid 1,000-row play-by-play sample through the production connector.

Repeat bounded checks with python examples/verify_live.py. This verifies projections, not every FantasyPros ranking endpoint. Historical notebook workflows remain outside this verification.

## Factor-model holdouts

2015–2023 stored weekly data, config.sean scoring; 36,118 rows. Models use fixed hyperparameters, earlier-season training and strictly past performance features. These metrics are a single chronological comparison, not a tuned external benchmark.

| Horizon | Holdout | Model MAE | Baseline MAE | Coverage |
|---|---:|---:|---:|---:|
| Season | 2021 | 54.99 | 59.14 | 70.17% |
| Season | 2022 | 57.19 | 58.97 | 71.33% |
| Season | 2023 | 56.66 | 55.52 | 68.14% |
| Weekly | 2021 | 5.85 | 6.10 | 98.55% |
| Weekly | 2022 | 5.65 | 5.99 | 98.60% |
| Weekly | 2023 | 5.47 | 5.68 | 98.26% |

Season baseline: previous-season total points. Weekly baseline: trailing four observed games. Coverage is within the supplied archived sample, not the entire NFL. Season models exclude players without a prior-season row; neither evaluation includes absent-game zero labels. The season model loses to baseline in 2023. Weekly improvements are modest and do not measure lineup wins.

Smoke tests produced 295 season forecasts, 219 weekly forecasts and a feasible seven-slot lineup. Those forecasts target historical demonstration fixtures, not current player advice. See MODELS.md for data and injury/rookie limitations.
