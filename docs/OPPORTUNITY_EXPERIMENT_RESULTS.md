# Snap share and scoring-opportunity experiment

Snap share produced a small improvement, but neither candidate earned production promotion. The hosted report and its forecasts remain unchanged.

| 2024 confirmation (5,746 player-games) | Baseline | Snap share | Snaps + opportunities |
|---|---:|---:|---:|
| Mean absolute error (points) | 4.738 | 4.719 | 4.722 |
| RMSE (points) | 6.503 | 6.482 | 6.485 |
| Start/sit pair accuracy | 56.29% | 56.43% | 56.33% |
| Pair regret (points) | 3.257 | 3.237 | 3.258 |

Snap share was selected using 2022-2023 development results before evaluating the 2024 confirmation season. The selected model reduced MAE by 0.019 points (0.40%), below the preset 2% requirement. Its paired week-bootstrap 95% interval for MAE change was -0.0388 to -0.0011 points. The combined candidate improved MAE by 0.34%, with an interval that included zero.

Snap share reduced pair regret by 0.020 points, but the 95% interval for that change was -0.108 to +0.064 points. That is insufficient evidence of a dependable start/sit edge. The 38,610 comparisons are dependent pairs from only 18 weeks, not independent trials.

## Method and coverage

- 2021 initial training; 36 development weeks in 2022-2023; 18 confirmation weeks in 2024. Each forecast trains on earlier weeks only. Earlier confirmation outcomes become available to subsequent weekly fits.
- Production estimator and scoring rules held fixed. Candidates add lagged 4/12 observed-game snap shares, then goal-line carries and inferred end-zone targets.
- All 23,339 source rows retained. Nineteen snap joins were missing; snap coverage exceeds 99.8% in each season. Missing data stays missing. No names were used to resolve IDs.
- Goal-line carry location was available for all joined rows; one player-game had unknown end-zone target depth. Plays without receiver IDs cannot be assigned to players (587-765 passes per season, potentially including throwaways). End-zone counts cover recorded receivers only.
- Excluded 373 development/confirmation rows without prior observed history, equally for all models.
- No same-week or future performance enters a forecast. Player-ID joins, missing coverage, invalid plays, fixture parity and leakage have regression tests. 121 Python tests pass; changed-file Ruff checks pass. Repository-wide Ruff still reports 265 pre-existing findings; this experiment does not clean up unrelated files.

## Limits and next work

This tests observed games, not missed games, actual historical fantasy rosters, or cross-position FLEX decisions. The 2024 confirmation season differs from the prior usage experiment holdout, but previously served as its training data. Historical corrections are not archived Wednesday snapshots. These findings concern weekly forecasting, not draft-day accuracy.

The next useful step is a role-change and availability experiment: identify team changes, returning starters, injured teammates and changes in snap/target opportunity using only timestamped information available before kickoff. First archive the weekly input snapshots and compare a simple recent-points benchmark. Only then test whether a more complex model improves actual lineup decisions. Keep draft evaluation separate, using season-level outcomes and value over replacement.

## Reproduce

Install `pip install -e ".[dev,model]"`. Supply the downloaded nflverse stats/aliases snapshot, `snaps-2021.csv` through `snaps-2024.csv`, and `play_by_play_2021.csv.gz` through `play_by_play_2024.csv.gz`. The protocol defines the sources, filters and promotion gate. Run:

```powershell
python -m fantasyfootball.opportunity_experiment --data work/opportunity-data --snapshot work/opportunity-data/stats/snapshots/8a3f1bc51404a9405604 --league work/hosted-specialists-preview/league/league-supported-offense.json --output work/opportunity-experiment-new
```

The command saves joined-input coverage, forecasts, paired decisions, selection, fold cutoffs, feature names, source/code SHA-256 checksums and dependency versions. Input paths are local and data must be downloaded separately. This run used NumPy 2.5.4, pandas 2.3.3, scikit-learn 1.9.1 and SciPy 1.18.1.

Source definitions: [nflverse snap counts](https://nflreadr.nflverse.com/articles/dictionary_snap_counts.html) and [nflverse play-by-play](https://nflreadr.nflverse.com/articles/dictionary_pbp.html).
