# Research notebooks

## Supported workflow

[Weekly Player Research](current/Weekly-Player-Research.ipynb) runs offline from the repository root or its notebook folder. Install `pip install -e ".[viz]"` in your notebook kernel environment. The checked-in sample is synthetic. Replace the input path, season and canonical player IDs to analyze your league-scored observed games.

The notebook delegates plotting/export to `PlotlyVisualizer`: weekly trends, empirical cumulative distribution and an offline HTML report with the underlying data table. It does not scrape, overwrite source data, infer DNPs or recommend lineups. Use the supported weekly planner for forecasts and start/sit decisions. The notebook's Python cells run in CI from an empty namespace; browser/kernel display behavior still needs manual review.

This migrates the historical player-distribution use case of `Who-Should-I-Start.ipynb`. It deliberately replaces the old smoothed density graphic with observed cumulative frequency, correctly labeled and accompanied by sample counts. The legacy scraping and machine-specific CSV-rewrite cells are not carried forward.

## Receiver usage migration

[Receiver Usage](current/Receiver-Usage.ipynb) replaces the target-share/air-yard-share calculation from the weekly visualization notebook. It calls `ReceiverUsage.summarize` and the shared `receiver_usage` chart. Team stints remain separate, unknown air yards invalidate the team air-yard denominator, and unidentified pass plays are counted in an audit. Two-point attempts and nullified plays are excluded. The sample is synthetic; notebook cells run in CI. The play-by-play matchup workflow is also migrated below; other play-by-play visualizations remain pending.

## Team matchup migration

[Team Matchups](current/Team-Matchups.ipynb) compares one offense and one defense using a shared play-by-play snapshot. It delegates dropback EPA, designed-rush EPA and sack rates to `TeamMatchups` and uses separate shared-library charts with explicit units and sample counts. Missing outcomes stay missing. Scrambles belong to dropbacks, not designed rushes. It does not reproduce the old mixed-provider fantasy-point rankings or claim to predict a game's score. The original notebook remains preserved.

## Neutral tendencies migration

[Neutral Tendencies](current/Neutral-Tendencies.ipynb) replaces the neutral passing-rate workflow. It uses an explicit filter (first/second downs, >120 half-seconds, offense WP 20-80%) and counts sacks/scrambles as dropbacks. Sample size and incomplete-context counts accompany the rate; a team without qualifying plays remains unknown. The notebook is descriptive, uses synthetic data by default, and runs with the other supported notebooks in CI.

## Historical inventory

These 18 notebooks remain unchanged as research records. Their output counts describe saved cells, not proof of reproducibility. Some reference moved modules, old provider pages, hard-coded seasons, local paths or source-writing cells. Do not run all legacy cells as a setup step. Migrate a specific computation into the package, test it, then create a small notebook calling that API.

| Notebook | Code cells | Cells with saved output | Status |
| --- | ---: | ---: | --- |
| [2019-Fantasy-Kernel-Density-Analysis.ipynb](2019-Fantasy-Kernel-Density-Analysis.ipynb) | 14 | 10 | Historical; not CI-executed |
| [2019-Fantasy-Relplot-Analysis.ipynb](2019-Fantasy-Relplot-Analysis.ipynb) | 14 | 9 | Historical; not CI-executed |
| [2019-Positional-Correlation-Analysis.ipynb](2019-Positional-Correlation-Analysis.ipynb) | 17 | 7 | Historical; not CI-executed |
| [2020-Target-Share-vs-Air-Yard-Share.ipynb](2020-Target-Share-vs-Air-Yard-Share.ipynb) | 13 | 3 | Historical; not CI-executed |
| [2020-TD-Regression-Candidates.ipynb](2020-TD-Regression-Candidates.ipynb) | 44 | 32 | Historical; not CI-executed |
| [2020-Top-30-Air-Yards-Density.ipynb](2020-Top-30-Air-Yards-Density.ipynb) | 9 | 4 | Historical; not CI-executed |
| [2020-Week-1-and-2-Target_and_Carry_Share-Analysis.ipynb](2020-Week-1-and-2-Target_and_Carry_Share-Analysis.ipynb) | 17 | 7 | Historical; not CI-executed |
| [2020-Week-1-Bootstrap-Resampling.ipynb](2020-Week-1-Bootstrap-Resampling.ipynb) | 9 | 5 | Historical; not CI-executed |
| [2020-Week-3-Target_and_Carry_Share-Analysis.ipynb](2020-Week-3-Target_and_Carry_Share-Analysis.ipynb) | 10 | 5 | Historical; not CI-executed |
| [2022-NFL-Team-Distribution-Vizzes.ipynb](2022-NFL-Team-Distribution-Vizzes.ipynb) | 7 | 5 | Historical; not CI-executed |
| [2022-NFL-Weekly-Vizzes.ipynb](2022-NFL-Weekly-Vizzes.ipynb) | 18 | 16 | Historical; not CI-executed |
| [Fantasy-Pros-Projections.ipynb](Fantasy-Pros-Projections.ipynb) | 64 | 38 | Historical; not CI-executed |
| [k-Estimator.ipynb](k-Estimator.ipynb) | 15 | 11 | Historical; not CI-executed |
| [Merged-DF-Analysis.ipynb](Merged-DF-Analysis.ipynb) | 23 | 13 | Historical; not CI-executed |
| [NFL-Team-Distribution-Vizzes.ipynb](NFL-Team-Distribution-Vizzes.ipynb) | 7 | 5 | Historical; not CI-executed |
| [NFL-Weekly-Vizzes.ipynb](NFL-Weekly-Vizzes.ipynb) | 16 | 14 | Historical; not CI-executed |
| [pro-football-reference-web-scrape-sample.ipynb](pro-football-reference-web-scrape-sample.ipynb) | 15 | 13 | Historical; not CI-executed |
| [Who-Should-I-Start.ipynb](Who-Should-I-Start.ipynb) | 29 | 15 | Historical; not CI-executed |

## Next migrations

- Remaining pace, efficiency and player graphics in `NFL-Weekly-Vizzes.ipynb`: isolate transforms and scoring contracts from live provider retrieval.
- Target/carry-share studies: reuse canonical IDs and explicit team denominators; test missing data and player transfers before publishing charts.
- Draft tier notebooks: use `DraftApplication` and the shared Plotly adapter rather than duplicating valuation or clustering code.

Generated outputs belong under ignored `work/`. Keep current notebooks free of saved outputs and credentials. Historical figures/data are retained until their provenance and replacement have been verified; no bulk deletion is part of this migration.
