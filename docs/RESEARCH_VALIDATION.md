# Research snapshot validation

Validated October 28, 2026 using cached public nflverse play-by-play files originally downloaded October 26. This is historical real-data validation, not a fresh live download, a forecast backtest, or visual browser approval. Each input SHA-256 matched its saved download manifest before processing.

All three research workflows processed all 32 teams in each season through regular-season week 18. Each season produced 192 matchup metric rows (32 teams x 2 units x 3 metrics). Receiver shares reconciled to one per team over identified targets; neutral counts reconciled to dropbacks plus designed runs. Chart objects built and serialized successfully. No missing matchup metric observations or incomplete neutral context were found in these snapshots.

| Season | Input rows (all season types) | Identified targets | Unidentified pass plays | Neutral plays | Receiver-team rows with unknown air-yard share |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2021 | 49,922 | 18,058 | 1,831 | 14,274 | 21 |
| 2022 | 49,434 | 17,306 | 1,999 | 15,285 | 0 |
| 2023 | 49,665 | 17,483 | 2,175 | 14,674 | 0 |
| 2024 | 49,492 | 17,013 | 2,041 | 14,513 | 0 |

Unidentified pass plays may include sacks or throwaways and are not automatically missing targets. The 2021 unknown shares are retained as unknown according to the incomplete/nonpositive denominator contract. No missing data was filled with zero. Aggregate results, source URLs, fetch times and checksums are saved in [validation/research](validation/research/); no roster data or full input dumps are published.

## Reproduce

```powershell
python -m fantasyfootball.research.validate work/opportunity-data/play_by_play_2024.csv.gz --season 2024 --through-week 18 --charts --expected-sha256 23370d5d10f8104d80d46a1fc5e61f4f6f5a3263fe96fe2dd629913cfcb08c06 --output work/research-validation/2024.json
```

Use the checksum for your chosen snapshot; a revised provider file should receive a new provenance record rather than silently retaining an old checksum. The command only reads a local input. `--charts` requires the `viz` extra and checks figure construction/serialization, not rendered appearance. The output cannot overwrite the input path. Failed validation does not write a success report.

## Bug found and fixed

The receiver transform originally validated two-point flags on every row before selecting pass plays. The 2024 snapshot contains 1,517 missing flags on end-of-play, no-play and kickoff rows, all irrelevant to target calculations. Validation now applies after the requested regular-season pass-play filter. Missing flags on eligible pass plays still raise. A regression test covers both behaviors.

## Generate an offline report

Install the `viz` extra, then choose the offense and opposing defense explicitly:

```powershell
python -m fantasyfootball.reports.research work/opportunity-data/play_by_play_2024.csv.gz --season 2024 --through-week 18 --offense NE --defense BUF --expected-sha256 23370d5d10f8104d80d46a1fc5e61f4f6f5a3263fe96fe2dd629913cfcb08c06 --output work/research-2024.html
```

The HTML embeds one Plotly bundle and works offline. It contains receiver usage across all teams, the selected historical offense/defense comparison, neutral tendencies, coverage notes, and complete underlying research tables. Unknown values remain visible in the tables. The source filename and checksum identify the input; season/week identify the observation window. It does not fetch data, send email or change forecasts.

`ResearchReport.write` and snapshot validation share `analyze_snapshot`, so they use the same transforms and invariant checks. The writer constructs the report before replacing an existing output and rejects output paths that resolve to the input file. Keep personal or league-derived reports under ignored `work/` or the private archive.
