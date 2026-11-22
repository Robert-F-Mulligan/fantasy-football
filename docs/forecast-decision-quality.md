# Forecast evidence and drop decisions

Trade reports retain the historical appearance-rate baseline, which is not an injury probability. Clearing an injury designation does not establish workload after a gap in recorded games.

Each player carries a last-observed season/week, sample count, current designation, and count of scheduled team games since their last observation. Byes do not count as missing observations. Missing records can reflect injury, inactivity, or incomplete ingestion; the report does not infer the cause. Only pre-forecast history is used.

Drop reviews compare historical participation with two explicit sensitivities for players without a designation but with missing recent games: full availability at current projected workload, and full availability with a trailing-12-game scoring-average floor. These are assumptions, not calibrated forecasts or confidence intervals. Known unavailable games and byes remain unavailable. Baseline projections are never overwritten.

The optimizer includes FLEX eligibility, bye coverage, depth, and current waiver alternatives. It assumes access to those alternatives; claim competition and reacquisition costs are not modeled. A one-point full-horizon tolerance identifies practically close choices; it is not a statistical significance threshold. Keeper leagues require a separate keeper-value review, and incomplete forecasts do not produce drop recommendations. Pick-package drops are illustrative roster-space assumptions, not automatic instructions.

Use `assess_drops(..., incoming=player_id)` to evaluate roster space after a specific acquisition. Without an incoming player it evaluates the current roster. Evidence is persisted in trade-report.json and restored by load_calculator; trade evaluations expose forecast_review flags.

Regression coverage includes cleared designations with stale history, future-data exclusion, byes, scenario-dependent ranking reversals, near ties, keeper safeguards, and unknown forecasts. These protections improve decision transparency; they do not establish predictive improvement. Promotion of a new availability model still requires chronological, paired evaluation against the existing baseline.
