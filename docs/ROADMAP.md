# Repository audit and roadmap

Audit date: October 24, 2026. PR #10 contains the refactor and the review fixes through d5a48ea. This document distinguishes completed cleanup from future work; the repo is not yet a fully automated current-season decision system.

## Cleanup completed in this pass

- Removed the two disabled dbt starter models and their sample schema tests. Their only model dependency was on each other, and the project already disabled them.
- Removed redundant .gitkeep files in the now-populated dbt macros and tests directories. Kept placeholders for genuinely empty directories.
- Stopped tracking output.csv, logs/dbt.log and fantasy_football_dbt/.user.yml. Their local copies remain on this machine; they are recoverable from Git history and ignored going forward. No code/notebook/config references to the root export were found in the audit.
- Ignored .venv, matching the environment directory used in the quick start.
- Removed the obsolete disabled-example configuration block.

These changes do not rewrite Git history or significantly shrink clone size. The previous refactor removed import-time execution and eager registration, but did not perform a wholesale legacy-file purge.

## What remains, and why

The tracked inventory before this cleanup contained 714 figure files (81.22 MiB), 67 data files (30.69 MiB), and 18 notebooks (17.63 MiB). These are working-tree sizes, not compressed repository history sizes. The source package is only about 0.25 MiB, so removing a handful of Python files will not materially reduce repository size.

Keep historical datasets: they are inputs to reproducible evaluations, not disposable outputs. Keep notebook research and figures until a curated archive has been reviewed. Separate reproducible figure outputs from reusable logos/sample assets before moving them. A later archive can use versioned external storage, without rewriting repository history unless explicitly desired.

Keep legacy draft, tiers, weekly tiers, nflfastr, nflteamh2h, fantasypros and ffcalculator modules for now: notebooks or other legacy modules still reference them. Their existence is not proof they work with current providers. The unsupported pfradv module imports a missing fantasyfootball.pfrgbg dependency and needs migration or explicit archival. It is not used by the new supported application path.

Keep the misspelled data_faceade module as a compatibility alias. Keep setup.py as the packaging shim. Keep both ingestion configurations: the package file is the installed default; config/data_config.json is an editable override documented in the README. Add a consistency check for shared defaults rather than deleting either blindly.

## Highest-priority engineering work

1. **Complete current data and a canonical player registry.** Reconcile provider IDs, rookies, free agents, team changes and duplicate names. Track source timestamps and completeness by season/week/position. Reject stale or incomplete draft pools. The verified FantasyPros preview is only 40 players; current factor-model evaluations use stored 2015–2023 data.
2. **Repeatable ingestion.** Upsert by stable dataset keys, record source snapshots/checksums, apply stat corrections, and make reruns idempotent. Current database append can duplicate data. dbt tests detect duplicate play keys but do not prevent their insertion.
3. **Clean-install CI.** Test the documented extras on supported Python versions, build/install the wheel outside the source directory, and run dbt against a small PostgreSQL fixture in isolated CI schemas. Protect main only after that workflow is reliable. No GitHub Actions workflow is currently tracked.
4. **Honest labels and evaluation.** Add scheduled-player and availability data to distinguish a bye, DNP, injury, missing record and true zero. Include all eligible players in evaluation, compare against current expert projections and simple baselines, and measure lineup regret and draft outcomes rather than only point MAE. The season model lost to its baseline on the 2023 holdout.
5. **Model/run provenance.** Record training cutoff, source versions, features, scoring rules, hyperparameters, metrics and dependency versions with each forecast. Add uncertainty calibration and drift checks before automated decisions.

## Features I would add, in order

| Priority | Feature | Useful behavior | Completion criterion |
|---|---|---|---|
| 1 | League and roster import | Loads scoring, starters, bench, IR, keepers and actual available players | Reproduces a known league's scoring and never recommends an already-rostered waiver player |
| 2 | Opportunity and availability forecasts | Uses snaps, routes, targets, carries, red-zone usage, depth-chart changes and timestamped injury reports | As-of joins pass leakage tests and improve held-out errors/calibration across positions |
| 3 | Live draft assistant | Tracks picks, team needs, scarcity, keeper costs and alternative picks | Simulates realistic opponents and compares draft-now vs wait-until-next-pick roster value |
| 4 | Weekly lineup and waiver planner | Handles locked games, late swaps, injuries, bye coverage, add/drop pairs and FAAB | Optimizes only legal roster moves, compares next several weeks, and explains the incremental value |
| 5 | Decision-focused dashboard | Shows projection ranges, uncertainty, data age, workload trends, roster impact and scenario changes | A user can understand and reproduce a recommendation without reading model code |

The current ADP survival heuristic is not an opponent draft simulator. The current lineup optimizer maximizes a single week's mean points; it does not implement late swaps, game locks by kickoff, acquisition costs, salary caps, correlations or multi-week planning. Those distinctions should remain explicit in UI and documentation.

Choose the league connector based on where the user's actual leagues live. Sleeper is a practical candidate when relevant: its documented API exposes league scoring, rosters, draft picks and transactions through a read-only interface (https://docs.sleeper.com/). This is an option, not an assumption that the user uses Sleeper. A CSV import remains the cross-platform fallback.

## Suggested next milestone

Build a complete player registry and a reproducible, current player-week dataset, then connect one real league. That foundation should precede another model family or a larger UI. The first product milestone should be one explainable draft board plus a weekly start/sit and waiver workflow using the user's exact scoring and roster.
