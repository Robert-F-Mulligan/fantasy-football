# Defense scoring coverage audit

Checked November 12, 2026 against live league scoring settings and the official nflverse weekly team-stat release. This is a source-coverage audit, not full defense-score reconciliation or a forecasting evaluation. DEF rankings remain disabled.

## Findings

The selected regular-season window, 2026 weeks 1-9, contains 272 team-games. Eight active scoring components have complete numeric candidate source fields. Ten active settings lack the necessary attribution, including six nonzero points-allowed tiers. See [aggregate evidence](validation/defense-scoring-coverage.json).

| Component | Candidate nflverse columns |
| --- | --- |
| Sacks | def_sacks |
| Interceptions | def_interceptions |
| Forced fumbles | def_fumbles_forced |
| Tackles for loss | def_tackles_for_loss |
| Safeties | def_safeties |
| Blocked kicks | def_punt_blocks + def_pat_blocks + def_fg_blocks |
| Defensive touchdowns | def_tds |
| Special-teams defense touchdowns | special_teams_tds |

These mappings need event-level and Sleeper reconciliation before use in complete scores. In particular, aggregate forced-fumble and touchdown coverage does not prove identical platform attribution.

Unresolved components are fourth-down stops, defensive fumble recoveries, special-teams forced fumbles and recoveries, and fantasy points allowed. Aggregate fumble recoveries are not substituted for defensive recoveries. Unknown nonzero settings are flagged rather than ignored. Individual offensive/special-teams and kicking settings are kept separate.

Sleeper's [points-allowed rules](https://support.sleeper.com/en/articles/4126495-how-are-points-allowed-calculated) exclude some opponent defensive scores while still charging conversions. A final score cannot safely replace fantasy points allowed. Sleeper also distinguishes [individual and team special-teams scoring](https://support.sleeper.com/en/articles/3278982-special-teams-scoring-options). The source is the [official nflverse team-stat release](https://github.com/nflverse/nflverse-data/releases/tag/stats_team); column documentation is in the [team-stat dictionary](https://nflreadr.nflverse.com/articles/dictionary_team_stats.html).

## Reproduce

Download the weekly team-stat CSV and supply a scoring-settings JSON or an existing import-report.json. Select the analysis window explicitly; the audit does not establish that games are final.

```powershell
python -m fantasyfootball.evaluation.defense --team-stats team-stats.csv --settings import-report.json --season 2026 --through-week 7 --output defense-audit
```

The output directory must be new. `coverage.json` records input hashes, observed weeks, missing/invalid fields and unresolved components without copying league identity or roster data. `candidate-components.csv` contains individual candidate component contributions, never a combined score. Missing values remain missing; they are not replaced with zero. Even complete field coverage leaves `ready_for_scoring` false until independent reconciliation exists.

## Next validation

Derive the missing components from attributed plays, test penalties/no-plays and turnover-return scoring edge cases, then reconcile component and total scores against Sleeper for finalized games. Separate rule changes and source corrections from model error. Only after reconciliation should a chronological DEF baseline and forecast comparison be considered for the optimizer.

## Component reconciliation

The optional `--sleeper-stats sleeper-defense-records.json` argument compares candidate counts against saved Sleeper regular-season `category=stat` DEF records. The JSON input is a list of records returned by `https://api.sleeper.com/stats/nfl/2026/{week}?season_type=regular`, concatenated across weeks and filtered to `player.position=DEF`. This stats endpoint is a research source, not part of the documented v1 league API contract. Save the response before analysis; the CLI hashes all inputs. Existing results are never overwritten.

```powershell
python -m fantasyfootball.evaluation.defense --team-stats team-stats.csv --settings settings.json --sleeper-stats sleeper-defense-records.json --season 2026 --through-week 9 --output defense-reconciliation
```

The source team-stat URL is `https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_2026.csv`. Obtain scoring settings from your league import. The published evidence contains capture time, source descriptions and hashes; it excludes league identity and rosters.

The November 12 snapshot comparison produced:

| Component | Explicit paired observations | Matches | Disagreements |
| --- | ---: | ---: | ---: |
| Sacks | 231 | 228 | 3 |
| Interceptions | 143 | 143 | 0 |
| Forced fumbles | 151 | 137 | 14 |
| Tackles for loss | 266 | 264 | 2 |
| Safeties | 2 | 2 | 0 |
| Blocked kicks | 16 | 16 | 0 |
| Defensive TDs | 15 | 9 | 6 |
| Special-teams TDs | 3 | 3 | 0 |

See [aggregate reconciliation evidence](validation/defense-component-reconciliation.json). Counts are component observations, not independent games. Sleeper records are sparse: absent fields are unknown, not implicit zeros. Consequently these paired matches do not establish complete scoring coverage, and comparing only reported events is not an accuracy estimate over all games. `component-comparisons.csv` retains every mismatch and unresolved row for investigation; aliases LAR/LA and WSH/WAS are normalized, and duplicate team-weeks are rejected.

Twenty-five component differences need event-level investigation before using these mappings in forecasts. This comparison does not establish which provider is correct, game finality, total score agreement, or historical league-rule consistency. DEF forecasts remain disabled. The next step is to inspect these identified plays and reconcile the ten unmapped active settings, rather than infer missing values or fit a forecast to inconsistent labels.

## Play-level investigation

The unified investigation command produces the coverage audit, explicit-provider reconciliation, stable discrepancy cases, and an optional attributed play ledger:

```powershell
python -m fantasyfootball.evaluation.defense_investigation --team-stats team-stats.csv --settings settings.json --sleeper-stats sleeper-defense-records.json --pbp play_by_play_2026.csv.gz --season 2026 --through-week 9 --output defense-investigation
```

Use the official snapshot at `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz`. All input bytes are hashed. Outputs include `discrepancy-cases.csv`, `event_ledger.csv`, `event_components.csv` and `event_comparisons.csv`, with JSON summaries. The output directory must not exist.

Candidate events cover explicit fourth-down failures on pass/run plays, simple opponent fumble recoveries and forced fumbles (separating punt/kickoff phases), and attributed defensive return touchdowns. No-play rows are excluded. Penalty dispositions, complex fumble sequences, missing flags and unsupported play types remain unresolved. Offensive recovery touchdowns and punt/kickoff return touchdowns are not counted as defensive touchdowns. These are research candidates, not established Sleeper edge-case rules.

`observed_source_count` is the supported event subset. A full-game `source_count` is unavailable unless a caller supplies `--complete-game-ids complete-games.json`, a JSON list of IDs whose complete play coverage was independently checked, and that component has no unresolved plays. A completed game alone is not proof of complete source coverage. Default runs do not attest coverage, so their event counts are not silently compared as complete totals.

The saved 23,822-play / 136-game window reproduced all six aggregate defensive-TD discrepancies as explicitly attributed defensive fumble-return touchdowns. Their game/play IDs are retained in [event evidence](validation/defense-event-investigation.json). This establishes a problem with using the aggregate field alone; it does not justify adding all aggregate fumble-recovery touchdowns, which can include other phases. Eleven forced-fumble cases remain numerically compatible with special-teams category separation, one retains a residual, and seven cases remain unexplained. Arithmetic compatibility never automatically resolves a case. Full scoring, penalty enforcement, sparse-provider zeros, points-allowed exclusions and forecast validation are still pending.
