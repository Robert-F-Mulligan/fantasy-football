# Schedule-aware weekly planning

The `weekly-plan` command produces **offensive research recommendations**, not a complete Sleeper lineup. K/DEF forecasts and exact special-teams scoring remain unfinished. It requires the `model` and `scraping` extras.

## Reproducible workflow

Refresh the canonical data with `sync-data`, then import the league again with `import-sleeper`. New imports retain each player's exact starter slot. Imports made before this feature must be refreshed.

```powershell
python -m fantasyfootball sync-weekly-context --output work/context-week7
python -m fantasyfootball import-sleeper LEAGUE_ID --season 2026 --team "Your Team" --snapshot work/live-data/snapshots/SNAPSHOT_ID --output work/league-week7
python -m fantasyfootball weekly-plan work/live-data/snapshots/SNAPSHOT_ID/weekly.csv --league-dir work/league-week7 --schedule work/context-week7/games.csv --players work/context-week7/players.json --season 2026 --week 7 --as-of "2026-10-24T16:00:00-04:00" --allow-partial-scoring --output work/plan-week7
```

Choose the current week and timestamp, and new output directories for each refresh. Refresh the player and roster snapshots close to the planning timestamp. A timestamp does not reconstruct historical injuries or roster assignments. The Sleeper bulk player download is fetched once per context snapshot; reuse it during development instead of fetching it for each candidate.

The optional `--allow-partial-scoring` flag explicitly acknowledges the unsupported categories recorded by the importer. Without it, incomplete offensive scoring blocks planning. The planner always excludes K/DEF slots. Other unknown player positions and missing availability block the recommendation.

## Rules and output

- Training rows are strictly before the requested week; partial results from the target week never enter training.
- Kickoffs use nflverse's Eastern local game times, converted to timezone-aware UTC.
- A started starter remains in the exact imported slot. A started bench player cannot be inserted. A locked FLEX player cannot be moved into RB or WR to make a lineup feasible.
- Reserve/taxi, out, doubtful, suspended and inactive players are excluded before kickoff. Questionable players remain eligible with a visible warning. This is a conservative policy, not proof of official game-day eligibility.
- Players with no scheduled game are excluded and labeled as a possible bye or incomplete schedule. Unknown teams/statuses block recommendations. Missing projections are errors, never zero-point guesses.
- `availability.csv` explains each roster decision; `projections.csv` contains eligible/locked offensive forecasts. `lineup.csv` is written only for a feasible lineup. `plan-report.json` reports success or a blocker, the training cutoff, scoring omissions, and input hashes. If a lineup is infeasible, inspect the report even when the command successfully wrote its audit files.
- Projections for already-started players are preweek estimates, not remaining-game forecasts or actual scores. Their inclusion is for slot constraints and is not actionable advice about those players.

This planner models ordinary starter locks. League-specific auto-substitution, player multi-position eligibility, commissioner overrides and best-ball formats are not implemented. Review the output before making changes; the software never submits lineup changes.

## Live validation, October 24, 2026

Bower Rangers' week-7 run used 2024-2026 data with training cutoff **2026 week 6**. Drake Maye remained locked in QB1 after New England's Thursday kickoff. Breece Hall's questionable designation was preserved. A feasible seven-slot offensive lineup was produced, excluding the kicker and team defense. Exact scoring still omits `st_ff` and `st_fum_rec`. The run is an integration check, not evidence of predictive accuracy.

Sources: [Sleeper API](https://docs.sleeper.com/), [nflverse schedule data](https://github.com/nflverse/nfldata/blob/master/data/games.csv). PostgreSQL/dbt were unchanged in this milestone and were not revalidated.
