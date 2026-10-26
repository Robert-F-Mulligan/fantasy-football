# Usage-feature experiment results

**Decision: retain the production model.** Usage shares plus trends produced a small improvement, but failed the pre-set 2% MAE improvement requirement. No new features were enabled in the Wednesday email.

## Confirmation results: 2026 weeks 1–6

| Model | MAE (points; lower is better) | RMSE | Pairwise choice accuracy | Mean pair regret (points) |
|---|---:|---:|---:|---:|
| baseline | 4.7749 | 6.5210 | 55.98% | 3.2064 |
| shares | 4.7678 | 6.5021 | 56.07% | 3.1688 |
| trends | 4.7472 | 6.4876 | 56.93% | 3.0723 |

The trends variant was selected using 2025 results before confirmation metrics were calculated. It reduced confirmation MAE by **0.0277 points (0.58%)**. The week-cluster bootstrap interval for candidate-minus-baseline MAE is **-0.06613 to -0.00002 points**: its upper endpoint barely clears zero, based on only six weeks. Treat this as weak preliminary evidence, not a robust edge.

Pairwise choice accuracy rose **0.96 percentage points**, and mean regret fell **0.1340 points (4.18%)**. The regret-change interval is **-0.3327 to +0.0405 points**, so a benefit is not established. The 13,785 pairs overlap and are not independent observations; uncertainty was resampled by whole week. There are 13,690 non-tied pairs for accuracy.

## Method

- Input: versioned nflverse snapshot ad296d51b938acb31ad6; supported Bower Rangers offensive scoring.
- Training starts with 2024. Refit before every held-out week using only earlier rows. Same tree settings, seed, cutoffs and evaluation population for all variants.
- Development: 18 weeks in 2025, 5,880 forecasts per variant. MAE: baseline 4.7207; shares 4.7220; shares plus trends 4.7104.
- Confirmation: six completed weeks in 2026, 2,009 forecasts per variant. Partial week 7 excluded. Across both periods, 239 rows without prior observed history were excluded.
- Shares: lagged 4/12-observed-game target, air-yard and team carry shares.
- Trends: shares plus last-observed shares, short-minus-long share changes, and target/carry/pass-attempt changes.
- Pairwise proxy: within each week and position, fixed baseline-ranked QB/RB/WR/TE candidate pools; compare pairs within three baseline projected points. Actual better score minus actual selected score defines regret. This does not replay real rosters or cross-position FLEX decisions.
- Leakage tests verify that changing current/future performance does not alter current features, and that fixture usage fields are ignored.

## Positional confirmation MAE

| Position | Baseline | Shares + trends | Change |
|---|---:|---:|---:|
| QB | 8.0286 | 7.8980 | -0.1305 |
| RB | 4.5994 | 4.5935 | -0.0058 |
| WR | 4.4978 | 4.4838 | -0.0140 |
| TE | 4.0156 | 3.9846 | -0.0310 |

## Limits and next experiment

This evaluates observed player-games, not DNP/injury outcomes, current historical rosters, or actual fantasy wins. Historical stat corrections come from the current snapshot; we do not reconstruct exactly what was published on a past Wednesday. Usage history crosses seasons and trades. Snap counts, routes, red-zone roles and weather were not tested. No interval calibration was changed.

The next stronger experiment should add snap participation and high-value opportunities, with explicit team/role resets and broader historical holdouts. Do not tune against these same six confirmation weeks repeatedly and then call them untouched validation.

## Reproduce

Run from the repository with the model dependencies installed:

```powershell
python -m fantasyfootball.experiments.usage_experiment --input work/hosted-specialists-preview/data/snapshots/ad296d51b938acb31ad6/weekly.csv --league work/hosted-specialists-preview/league/league-supported-offense.json --output work/usage-experiment-rerun
```

Use a new output directory. The runner saves forecasts, all comparison pairs, feature coverage, training cutoffs, input/code checksums, package versions and promotion gates. The data snapshot is ignored locally; preserve it to reproduce this exact run.
