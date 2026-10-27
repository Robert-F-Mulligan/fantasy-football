# Role-change experiment results

Workload momentum improved weekly point forecasts modestly, but did not meet the 2% improvement gate. Production forecasts and the Wednesday email model remain unchanged.

| 2024 exploratory evaluation | Baseline | Momentum | Momentum + competition |
| --- | ---: | ---: | ---: |
| Mean absolute error (points) | 4.738 | 4.667 | 4.672 |
| RMSE (points) | 6.503 | 6.438 | 6.451 |
| Close-pair decision accuracy | 56.29% | 57.03% | 56.71% |
| Mean pair regret (points) | 3.257 | 3.186 | 3.219 |

Momentum was selected on 2022–2023 before computing this run's 2024 metrics. It reduced MAE by 0.0705 points (1.49%). Its paired week-bootstrap 95% interval for MAE change was -0.1008 to -0.0429 points. The pair-regret difference interval was -0.1587 to +0.0165 points, so this does not establish a reliable lineup-selection benefit.

The candidate passed the paired-MAE, per-position and pair-regret numerical gates, but failed the required 2% overall MAE improvement. There were 5,746 evaluated player-games and 38,610 dependent same-position comparisons across 18 weeks. Those comparisons are not independent trials or actual league lineup decisions.

## What was tested

Last observed snap share, target share, carries and targets, plus the difference from the preceding three observed games (at least two required). The second candidate also uses historical same-position team carry/target shares. Every feature is shifted before use. Tests cover same-week/future leakage, fixture parity, missing values and duplicate IDs.

Training expands chronologically from 2021. Model hyperparameters and league scoring match the existing experiment harness. Historical data came from the existing opportunity experiment snapshot; source construction and coverage are documented in [its protocol](OPPORTUNITY_EXPERIMENT_PROTOCOL.md). See the [role protocol](ROLE_EXPERIMENT_PROTOCOL.md) and [machine-readable results](role-experiment-results.json) for input/code hashes, coverage, weekly folds and dependency versions. A formatting-only reproducibility run produced the recorded final-code result; no candidates or hyperparameters were adjusted after seeing metrics.

## Limits and next step

2024 was previously inspected in the opportunity experiment. This is exploratory reuse, not an untouched holdout, and even passing numerical gates would not justify production promotion. Inputs are corrected historical data, not as-published Wednesday snapshots. Players without prior observations and DNPs are excluded; historical windows can cross teams, seasons, byes and absences.

This tests workload changes, not injury status, returning starters, current teammate absences or charted routes. Historical injury feeds do not reliably preserve Wednesday observations, so injury effects cannot be evaluated honestly with those feeds. Continue collecting timestamped private snapshots and evaluate those prospectively. Keep season-long draft validation separate from weekly results.
