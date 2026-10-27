# Repository roadmap

Updated October 27, 2026. This is a research and decision-support platform; it never submits lineup changes or transactions.

## Working now

- OOP application/domain boundaries, provider adapters, league scoring, draft valuation, offensive factor models and constrained lineup optimization.
- Versioned nflverse snapshots with checksums and canonical player IDs; live Sleeper league/roster import for Bower Rangers.
- Offensive weekly planning with RB/WR/TE FLEX eligibility, exact starter-slot kickoff locks, reserve/injury checks and chronological training.
- HTML/plain-text email reports, offensive prediction ranges checked on later weeks, and GitHub-hosted Wednesday 10 a.m. Eastern delivery. Run 40201365106 sent the first hosted report; the user confirmed inbox receipt. The duplicate desktop schedule is paused.
- Clean-install Python 3.10/3.12 tests and wheel builds. Changes to main trigger email-free report preparation.
- Specialist report section: league-scored kicking-only baselines, kicker/defense schedule and status context, explicit assigned offensive slots. Defense point forecasts remain unavailable.

## Next milestones, in order

1. **Validate defense and full scoring.** Reconcile play-level defense/special-teams events against Sleeper, including points-allowed exclusions, fourth-down stops, tackles for loss, forced/recovered fumbles and return touchdowns. Do not substitute final game scores for fantasy points allowed. Add K/DEF forecasts to the full optimizer only after scoring and comparative forecast evaluation justify them.
2. **Availability-aware evaluation.** Private local pregame evidence capture and verification are implemented; hosted retention supports a scoped deploy key and verified private Git pushes; one-time owner credential setup activates it. Historical injury-input audit rejects current files for Wednesday backtesting because timestamps are missing or later than the cutoff (see PREGAME_EVIDENCE.md). Distinguish DNP, bye, injury, missing observation and true zero. Evaluate all eligible players, expand rolling holdouts, compare against simple and expert baselines, and track lineup regret. Offensive ranges currently exclude DNP risk; kicker estimates have no calibrated intervals.
3. **Idempotent storage and database CI.** Upsert on stable keys, apply corrections safely, and test dbt against an isolated PostgreSQL fixture in CI. Prior local PostgreSQL/dbt verification passed; the email workflow does not use PostgreSQL. Keyed correction imports and isolated PostgreSQL/dbt CI are implemented; see DATABASE_INGESTION.md. Legacy append remains opt-in compatible and can still duplicate rows. Existing production tables need an audited key migration before enabling upsert.
4. **Weekly waiver planning.** Position/FLEX rankings and budget-capped FAAB guidelines are implemented, with Tuesday delivery. One-week add/drop what-if comparisons are implemented with protected starters and kickoff locks. Next: current role validation and future bye coverage. Preserve kickoff locks and provide incremental roster value rather than only standalone rankings.
5. **Draft decision evaluation.** Build complete current draft pools, backtest season forecasts and compare realistic draft strategies. The season model previously lost to its baseline on the 2023 holdout. ADP survival is a heuristic, not an opponent simulator.
6. **Reproducible notebook migration.** Move reusable notebook computations into package APIs, retain concise research notebooks, regenerate chosen visuals, then archive obsolete outputs. Refresh workflow action pins and add dependency locking as operational follow-up.

## Cleanup status

Removed disabled dbt starter examples and redundant placeholders; untracked generated output.csv, dbt.log and dbt .user.yml while preserving local copies. Added virtual environment ignores. This was targeted cleanup, not a wholesale legacy purge or Git history rewrite.

The earlier inventory contained 714 figures (~81 MiB), 67 data files (~31 MiB), and 18 notebooks (~18 MiB). These historical assets have not been bulk-deleted or fully migrated. Keep reproducible source data and useful research; separate generated figures from reusable assets before archiving. Legacy modules remain where notebooks reference them; pfradv's missing pfrgbg dependency needs explicit migration or archival. Keep the data_faceade compatibility alias and setup.py packaging shim until consumers migrate.

## Specialist validation limits

Kicking scoring matched 68 available rostered kicker scores from this league's 2026 weeks 1?6. A small chronological weeks-5/6 check covered 57 forecasts: baseline MAE 4.27 points versus 4.31 for the recent league mean. This does not establish a predictive advantage. The baseline uses eight observed current-team games with four games of league-average shrinkage; it does not model weather, opponent, injury probability or rare offensive scoring by kickers.
