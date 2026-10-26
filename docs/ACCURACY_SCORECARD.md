# Weekly forecast accuracy scorecard

Scorecards compare the production forecast with the mean of each player's previous four observed games, calculated solely from the sealed forecast archive. Both methods use the same resolved, pregame player observations. Outputs include MAE, RMSE, signed bias, counts by position, and conditional prediction-range coverage/width. Positive bias means overprediction; lower MAE/RMSE is better.

## Automatic private evaluation

After preparing and archiving a report, the private archive publisher selects the earliest retained capture for each league/roster/week before inspecting outcomes. It evaluates prior weeks only when the incoming archive includes completed schedule scores, at least eight hours have passed since the last kickoff, and the stats include both teams from every scheduled game. These gates cannot rule out later official statistical corrections; later source snapshots produce separate evidence revisions.

Observed box-score rows are scored with the forecast archive's supported league rules. Missing player records stay unresolved: they are never inferred healthy, DNP, or zero. A true zero is retained when a box-score row supports it. Missing outcomes may prevent complete lineup-regret calculations even when individual point errors are available.

Private ZIPs appear under `scorecards/SEASON/week-WW/` in the evidence repository. Each contains:

- `scorecard.html`: readable summary.
- `scorecard.json`: metrics, denominators, source/evaluator hashes and limitations.
- `player-results.csv`: per-player predictions, baseline, eligibility and outcome status.
- `outcomes.json`: observed scoring evidence used by the automatic evaluator.
- `outcomes-template.json`: template for explicitly resolving remaining participation evidence.

The public workflow uploads no scorecard artifacts and prints no player results. Every pushed scorecard blob is fetched and verified, alongside the original evidence archive. Existing credentials and schedule are reused. There is no new email or lineup submission.

This deterministic earliest-capture policy includes development/dry-run captures. It does not imply the selected report was sent on Wednesday. Do not cherry-pick a later run because its predictions looked better. A future report-type field can distinguish scheduled Wednesday forecasts prospectively.

## Lineup decisions

The scorecard compares the actual points from the archived recommendation, the recent-four-games baseline lineup, and the highest-scoring hindsight lineup feasible under the same saved roster slots. RB/WR/TE FLEX eligibility and exact kickoff locks are preserved. Already-locked players contribute the same fixed outcome to every lineup and are excluded from point-forecast accuracy if captured late.

Lineup regret is withheld unless all movable candidates have pregame evidence, all eligible/locked candidate outcomes are resolved, baseline history is available, and the archived assignment is feasible. The bench is included in this completeness requirement. Excluding an unresolved bench alternative could artificially improve reported regret. Regret measures archived advice, not whether the manager actually submitted that lineup. K/DEF remain excluded.

## Run locally

```powershell
python -m fantasyfootball.scorecard --archive path/to/forecast.zip --output work/scorecard-week8
python -m fantasyfootball.scorecard --archive path/to/forecast.zip --outcomes work/final-outcomes.json --output work/scorecard-week8-final
```

Without finalized outcomes the report shows pending evidence rather than zero accuracy. Each output folder must be new, preserving older evaluations. The template includes the required archived scoring fingerprint. For each resolved player, supply a source reference and timezone-aware finalization time after kickoff; set status to `played` or explicitly verified `dnp`. A DNP must have zero points. Unresolved records must have null points. Finalization times in the future and mismatched weeks/scoring are rejected. The program validates this contract but cannot independently certify a caller's evidence claim.

## Current evidence and limits

The initial local week-7 archive was captured after rostered players' kickoffs. Its real scorecard correctly contains zero pregame comparisons, not a claimed forecasting improvement. The first upcoming pregame captures and subsequent completed games will supply useful evidence.

There are no statistical-significance or promotion claims from a one-week scorecard. Prediction ranges were designed conditional on playing, so confirmed DNPs are excluded from range coverage; point errors are reported separately for all resolved players and played-only players. The supported scoring may omit special-teams categories disclosed by the original report. Models and production recommendations are unchanged.
