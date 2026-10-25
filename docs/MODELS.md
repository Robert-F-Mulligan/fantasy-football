# Factor models and weekly lineup optimization

Install the `model` extra. The CLI accepts weekly history with stable IDs, year/season, week, position, opponent (`opp`), age if known, passing attempts/yards/TDs/interceptions, rushing attempts/yards/TDs, receiving targets/receptions/yards/TDs and all configured scoring stats. Only regular-season QB/RB/WR/TE rows are supported.

## Features and evaluation

The weekly model uses shifted 4- and 12-game workload and production, production trend, prior age, prior games, yards per target/carry, position, and the opponent's previous eight observed weeks of points allowed to that position. Opponent outcomes are grouped by week before the join, and the join excludes the forecast week. This is observed player-level production from the supplied sample, not a schedule-adjusted team-defense metric.

The season model uses prior-season volume, touchdowns, efficiency, games played, age, production trend and prior-season position. Outcomes and position changes from the target season cannot influence features. Each horizon uses regularized histogram gradient boosting with fixed settings and random early stopping disabled. The model is fitted separately for each chronological holdout. Weekly features update as previous games in the holdout season become known, but model weights remain fixed for that holdout season.

Rookie season projections are excluded because no previous-season record exists. Weekly cold starts can be predicted with missing historical features and expose `history_games=0`; treat them as weakly supported. The models predict observed player-game outcomes, not the probability a player plays. A scheduled-but-inactive player must be excluded before lineup selection. Missing games, injuries, snaps, depth-chart changes, weather and current betting lines are not inferred. Future use needs current data and explicit, timestamped context.

Neither model supports uncertainty intervals or win-probability optimization. The optimizer maximizes expected projected points. It does not model correlated player outcomes, waivers, salaries, or multi-week roster decisions.

## Commands

```powershell
python -m fantasyfootball evaluate-factors weekly.csv --horizon weekly --league league.json --output work/weekly-metrics.csv
python -m fantasyfootball evaluate-factors weekly.csv --horizon season --league league.json --output work/season-metrics.csv
python -m fantasyfootball forecast weekly.csv --horizon season --season 2027 --league league.json --output work/season-projections.csv
python -m fantasyfootball forecast weekly.csv --horizon weekly --fixtures upcoming.csv --league league.json --output work/weekly-projections.csv
python -m fantasyfootball lineup my-roster-projections.csv --slots examples/lineup-slots.json --excluded injured_player --locked must_start --output work/lineup.csv
```

Upcoming fixtures need player_id, player_name, pos, season, week and opp. They must describe exactly one week strictly after the historical cutoff. All columns containing outcomes in a fixture input are ignored. Filter your candidate CSV to your own roster before optimizing. Specify explicit eligible positions for every slot; SUPERFLEX is expressed by including QB in that slot's eligibility. Locked players must appear exactly once and excluded players cannot start. Infeasible lineups raise an error.

Forecasts return the same player/projection columns consumed by the draft CLI. Supply a sufficiently deep and eligible pool; supplement rookies using a separately sourced model before draft valuation.

Reproduce repository evaluations with `python examples/evaluate_factors.py`. It uses config.sean scoring on 2015–2023 stored weekly rows and evaluates 2021–2023. These archived samples are not complete current NFL rosters, and season coverage is approximately 68–71%. The season model loses to prior-season points on the 2023 holdout. See VALIDATION.md for measured results; do not assume universal superiority.


## Entirely missing training features

The current nflverse weekly input has no age values. Training excludes columns with no observed values in the training partition and retains that column selection for prediction. Partially missing columns retain native estimator missing-value handling. Each chronological evaluation fold selects its columns from its own training rows; future/holdout availability cannot influence the schema. Weekly plan metadata lists `dropped_training_features`. Training fails clearly if no observed feature remains.

This avoids scikit-learn 1.9.1's histogram-binning failure on an all-missing column (`window shape cannot be larger than input array shape`). The original failure was reproduced with NumPy 2.5.4, pandas 2.3.3, scikit-learn 1.9.1 and SciPy 1.18.1; corrected live report preparation passed on that stack. Hosted and CI jobs now print the installed model-library versions to aid diagnosis.
