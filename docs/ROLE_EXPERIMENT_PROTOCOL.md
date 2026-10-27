# Role-change experiment protocol

Frozen before running this candidate: compare the existing weekly baseline with (1) last observed snap share, target share, carries and targets, plus each value minus its preceding three observed games (at least two required); (2) those signals plus last/change in observed same-position team carry and target shares.

All features use strictly earlier player-games. Current-game outcomes, teammate activity and fixture usage must not affect a forecast. Missing shares stay missing. The features are not injury indicators. Historical feeds failed the prior Wednesday availability audit; do not reconstruct historical Wednesday injuries using final injury statuses.

Use the existing opportunity experiment input (2021–2024) and the same league scoring and production estimator hyperparameters. Start training in 2021, expand training before each week, select the lower-MAE candidate on 2022–2023, and report 2024 separately. This reuses a previously inspected evaluation year: it is exploratory, not an untouched confirmation set. No tuning or reruns based on its results; production stays unchanged even if numerical gates pass.

Use the existing gates: at least 2% MAE improvement, paired week-bootstrap 95% MAE difference interval below zero, no position more than 2% worse, and close-pair regret no more than 2% worse. Record feature coverage, input/code hashes and dependency versions. These observed-game metrics do not measure DNP prediction, actual league lineup value, or FLEX decisions. Future promotion requires contemporary prospective evidence.

Run:

```powershell
python -m fantasyfootball.experiments.role_experiment --input work/opportunity-experiment-v1-input.csv --league work/hosted-specialists-preview/league/league-supported-offense.json --output work/role-experiment-v1
```
