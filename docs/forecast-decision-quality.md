# Forecast evidence and drop decisions

Trade reports retain the historical appearance-rate baseline, which is not an injury probability. Clearing an injury designation does not establish workload after a gap in recorded games.

Each player carries a last-observed season/week, sample count, current designation, and count of scheduled team games since their last observation. Byes do not count as missing observations. Missing records can reflect injury, inactivity, or incomplete ingestion; the report does not infer the cause. Only pre-forecast history is used.

Drop reviews compare historical participation with two explicit sensitivities for players without a designation but with missing recent games: full availability at current projected workload, and full availability with a trailing-12-game scoring-average floor. These are assumptions, not calibrated forecasts or confidence intervals. Known unavailable games and byes remain unavailable. Baseline projections are never overwritten.

The optimizer includes FLEX eligibility, bye coverage, depth, and current waiver alternatives. It assumes access to those alternatives; claim competition and reacquisition costs are not modeled. A one-point full-horizon tolerance identifies practically close choices; it is not a statistical significance threshold. Keeper leagues require a separate keeper-value review, and incomplete forecasts do not produce drop recommendations. Pick-package drops are illustrative roster-space assumptions, not automatic instructions.

Use `assess_drops(..., incoming=player_id)` to evaluate roster space after a specific acquisition. Without an incoming player it evaluates the current roster. Evidence is persisted in trade-report.json and restored by load_calculator; trade evaluations expose forecast_review flags.

Regression coverage includes cleared designations with stale history, future-data exclusion, byes, scenario-dependent ranking reversals, near ties, keeper safeguards, and unknown forecasts. These protections improve decision transparency; they do not establish predictive improvement. Promotion of a new availability model still requires chronological, paired evaluation against the existing baseline.

## Acquisition-specific roster space

Pick offers attach a cached `drop_review` for each incoming player, reused across pick rounds. This is distinct from evaluating the current roster: the new player can change which bench slot is expendable. The trade brief shows the post-acquisition near-ties and scenario costs once per target. The selected pick-package drop remains illustrative; keeper rights and forecast flags still require review.

For a saved private report:

```powershell
python -m fantasyfootball.trading --plan path/to/plan --review-drops-for CANONICAL_PLAYER_ID --output acquisition-review.json
```

This mode makes no offer and needs no partner or pick selection. Older snapshots without forecast evidence return an explicit unavailable result. Unknown keeper configuration defaults to review, not assumed redraft eligibility.
