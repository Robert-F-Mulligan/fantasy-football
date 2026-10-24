# Live player data and Sleeper import

Install the `scraping` extra for HTTP access. All league operations are read-only; no login, roster transactions, or lineup changes are performed.

## Refresh current data

```powershell
python -m fantasyfootball sync-data --seasons 2024 2025 2026 --roster-season 2026 --minimum-week 7 --output work/live-data
```

Use the snapshot path printed by the command below. `current.json` points to the latest successfully validated snapshot. The content-addressed bundle contains canonical players, provider aliases, ID conflicts, roster rows without GSIS IDs, weekly stats, and a manifest with source URLs, fetch dates, checksums, and observed coverage. Identical downloads reuse the snapshot. Corrupt snapshots or failed refreshes do not replace the current pointer. Source bytes are checksummed; transformed CSVs, not raw HTTP payloads, are retained.

The current nflverse feed is `stats_player/stats_player_week_{season}.csv`. The older `player_stats` release stops at 2024. Weekly records are filtered to regular-season QB/RB/WR/TE and adapted to the existing model input schema. Provider fantasy-point totals are excluded so league weights can be applied.

`--minimum-week` checks the maximum observed week in each requested season. It does **not** prove that all games in that week have finished or that all player records are present. Current roster metadata must not be used as historical as-of features. DNP labels, injuries, game schedules and kickoff locks require separate sources.

## Import a Sleeper league

```powershell
python -m fantasyfootball import-sleeper LEAGUE_ID --season 2026 --team "Your Team" --snapshot work/live-data/snapshots/SNAPSHOT_ID --output work/my-league
```

The destination must be new to preserve prior imports. The importer verifies NFL and season, matches a unique team name or username, and finds its owned or co-owned roster. It exports all league rosters, your roster, full and offensive slot eligibility, and a scoring/identity audit. IDs are joined explicitly through GSIS, PFR, ESPN, Sleeper and Yahoo aliases; names are never used to join players. Roster-only GSIS players are retained with their source marked. Ambiguous aliases and unmatched players remain visible. FantasyPros IDs currently require an additional authoritative crosswalk.

`league-supported-offense.json` is an **approximate offensive scoring configuration** when the audit lists unsupported categories. Read `import-report.json` before using it. All original scoring rules are preserved there. K/DEF scoring is excluded from the offensive model, and unrecognized nonzero categories are reported. No claim of exact scoring or a complete lineup recommendation is made. Unknown roster slots are reported; draft configuration export is withheld for unsupported slot shapes, including superflex, while explicit optimizer slots retain known eligibility.

For an exact full-league model, the next work is special-teams event attribution, K/DEF projections, availability/schedule data, and comparison against Sleeper's scored matchups. Do not treat imported starters as locked players or use a partial week's results as a completed training season.

Sources: [nflverse player loader](https://nflreadr.nflverse.com/reference/load_players.html), [nflverse stats loader](https://github.com/nflverse/nflreadr/blob/main/R/load_stats.R), [Sleeper API](https://docs.sleeper.com/).

## Validation on 2026-10-24

- Live refresh: 5,864 player-weeks in 2024, 6,037 in 2025, and 2,112 in 2026 (observations through week 7); 14,013 rows passed league-weighted scoring and model input validation.
- Player registry: 24,861 source players plus 189 current roster-only GSIS players; one roster entry without GSIS retained separately.
- Authorized Sleeper league import matched the requested season and team. All 14 individual players on the selected roster resolved; its team defense remained unmatched. Across the league, 12 defense identifiers and one individual identifier were unmatched.
- Nonzero individual special-teams forced fumbles and recoveries are reported as unsupported; K/DEF predictions are not implemented.
- Python regressions cover schema validation, ID ambiguity, duplicate ownership, season mismatch, partial scoring disclosure, snapshot reuse/corruption, and preservation of the current pointer after failure.
- This milestone does not change PostgreSQL or dbt; their live validation was not rerun.
