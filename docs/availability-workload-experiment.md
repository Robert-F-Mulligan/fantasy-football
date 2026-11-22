# Availability and workload experiment

## Protocol

Research only; production predictions and scheduled emails are unchanged.

- Historical input: completed 2022-2025 regular-season weekly offensive statistics and schedules, scored using the supplied league configuration.
- Candidate universe: players with at least four prior statistical appearances, observed in the current season, on their last observed team with a scheduled game. No future debutants. Missing rows count as zero only where the team has at least five observed offensive statistical records in the completed forecast week. Transfer mismatches are excluded and counted.
- Training: expanding pre-week appearance/workload panel; the existing conditional point model uses its rolling two-season history. All predictors are strictly pre-week. Byes do not count as missed opportunities.
- Baseline: existing FactorModel conditional points multiplied by the last-eight-team-opportunity Laplace-smoothed appearance rate used in ROS valuation.
- Arms: learned appearance probability only; learned conditional workload only; both. The small boosted models use prior appearance rate, prior-game appearance, gap length, prior 4/12-game points, recent carries/targets, prior sample count, and position.
- Selection: lowest overall MAE in 2024 among the three candidates. Freeze selection before evaluating 2025; weekly refitting can use only outcomes already observed before that week's kickoff.
- Primary confirmation outcome: selected candidate minus baseline MAE on 2025 player-weeks. Negative is better. Report a paired 95% moving-block bootstrap interval with four-week blocks and 4,000 fixed-seed resamples.
- Secondary, descriptive outcomes: RMSE, appearance Brier score, prior-gap cohort MAE, and synthetic close start/sit decision regret. Pairs use the existing position pool caps and a maximum three-point baseline difference. These are not actual roster or waiver outcomes. Other arms' confirmation results are exploratory, not alternate winners.

The historical data does not establish medical availability. It lacks frozen pregame injury designations, inactive lists, weekly roster ownership, and clinical return-to-play information. Missing statistics may reflect injury, inactivity, retirement, a team change, or ingestion gaps. The prior-gap cohort includes players who remain absent, not only eventual returners. 2025 has appeared in other repository experiments, so it is a chronological confirmation season, not an untouched research lockbox.

No production promotion follows automatically from this experiment, even with a favorable interval. Archived prospective forecasts and pregame injury evidence are needed before promoting a medical-availability or returning-player model.

## Reproduce

```powershell
python -m fantasyfootball.experiments.availability_experiment --input weekly.csv --schedule games.csv --league league-supported-offense.json --output new-private-output-directory
```

The output directory must not already exist. It contains the pre-confirmation selection, frozen per-week predictions and training cutoffs, source hashes, cohort counts, paired metric intervals, and explicit limitations. Keep per-player forecasts private; publish only aggregate results.

## Results: completed 2025 confirmation

The combined arm was selected on 2024 before confirmation. Confirmation contains 7,479 player-weeks across 17 weekly cohorts (Weeks 2-18). The existing baseline's conditional scoring model is retained for the availability-only arm.

| Metric | Baseline | Selected combined model | Change |
| --- | ---: | ---: | ---: |
| Overall MAE | 4.176 | 3.932 | -0.244 points (-5.85%) |
| Overall RMSE | 6.189 | 5.961 | -0.228 points |
| Synthetic close-choice regret | 3.356 | 2.966 | -0.390 points (-11.61%) |
| Appearance Brier score | 0.1604 | 0.1367 | -0.0237 |

The selected model's paired four-week-block 95% MAE-difference interval is **[-0.295, -0.199]** points. The descriptive regret-difference interval is **[-0.524, -0.281]**. These are intervals for average differences, not individual-player prediction intervals. There are only 17 weekly clusters, and blocks do not model every form of season-long dependence.

### Why this is not a returning-player fix

| Diagnostic cohort | Rows | Baseline MAE | Combined MAE | MAE difference interval |
| --- | ---: | ---: | ---: | --- |
| Recorded appearance after a prior gap | 580 | 3.349 | 3.332 | [-0.221, +0.140] |
| Still absent after a prior gap | 1,556 | 2.588 | 1.249 | [-1.682, -1.174] |
| No prior gap | 5,343 | 4.728 | 4.778 | [+0.015, +0.075] |

The first two rows are **post-outcome diagnostic slices**, not cohorts available to the model before kickoff and not separate confirmatory hypotheses. The gain after gaps comes mainly from continued absences. For observed returners, signed prediction bias worsens from -0.874 to -2.340 points, while the MAE difference interval includes zero. The no-gap cohort's MAE also worsens slightly.

**Decision: retain production baseline and scenario safeguards.** This experiment provides evidence for better scoring-absence prediction in this historical cohort; it does not validate medical availability, post-clearance workload, or actual league lineup/drop performance. Next work should acquire timestamped pregame injury/inactive and roster evidence, then test observed returners prospectively with conditional workload and expected points evaluated separately.

Aggregate machine-readable results: [availability-workload-v1.json](research/availability-workload-v1.json). Per-player forecasts remain in the private experiment output. No email or production model was changed.
