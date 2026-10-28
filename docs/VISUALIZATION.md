# Visualization contracts

`fantasyfootball.reports.visualization.PlotlyVisualizer` is the supported interactive chart adapter. It returns figures without opening browsers or changing global Plotly defaults. The email renderer in `reports/reporting.py` uses HTML tables because email clients do not reliably execute JavaScript. Keep Plotly optional; hosted email must work without the viz extra.

## Data and meaning

- Draft charts validate finite points, ranks, tiers and supplied ADP; unknown ADP stays unknown. Duplicate player IDs are rejected. Charts and the data table use value rank with player ID as a stable tie-breaker, regardless of input row order.
- Horizontal draft bars preserve rank across position traces and include zero. Their lengths show projected season points, not value over replacement; the scatter chart shows replacement value separately.
- Weekly charts display integer NFL weeks and fantasy-point units. Missing observations break lines instead of implying zero or connecting across missing weeks. Filter to one season before plotting.
- Position symbols and player line styles supplement color. Reports include descriptive text, links to the underlying table and escaped labels. This improves accessibility but is not a claim of full WCAG conformance; keyboard and screen-reader testing remains necessary.
- Email uncertainty displays use a shared point scale and numeric alternatives. Historical error ranges are prediction ranges, not confidence intervals on the mean or probabilities of beating another player. Preserve the coverage sample size, observed coverage and DNP limitations alongside the graphic. Never invent a range for unsupported players.

## Export and review

HTML exports embed one Plotly.js bundle for offline use, use stable chart IDs, declare UTF-8 and the page language, and include a viewport tag. Identical data produces identical HTML within the same dependency versions. Pin the environment when comparing exported artifacts across time. Personal league reports remain local or in the private archive.

For chart changes, run `pytest tests/test_visualization.py`, verify ordering and missing-data semantics, and inspect a generated HTML report at desktop and narrow widths. Test mathematical/semantic properties rather than snapshots of the entire vendor bundle. Legacy exploratory notebooks are historical artifacts; new reusable plotting belongs in this adapter rather than copied notebook cells.

References: [Plotly HTML export](https://plotly.com/python/interactive-html-export/), [W3C complex chart text alternatives](https://www.w3.org/WAI/tutorials/images/complex/).

## Historical weekly research

`weekly_distribution` draws an empirical cumulative frequency curve: tied scores share a jump, negative points are retained, and the vertical scale is 0-100%. It describes supplied observed games, not future outcome probabilities. `write_weekly_report` exports this and the trend chart with an escaped data table. The supported notebook in `notebooks/current` calls these APIs without embedding plotting or export logic.

## Receiver usage

`ReceiverUsage.summarize` consumes the canonical nflverse receiver_player_id/receiver_player_name fields, explicit two_point_attempt flags and unique game_id/play_id keys. Select a season and through_week explicitly. The denominator is identified receiver targets, not all pass attempts. The audit counts unidentified pass plays (which may include sacks/throwaways); it does not guess how many are missing targets. Receiver-team stints remain distinct. Current LA/LAR and JAX/JAC aliases are normalized.

Signed air yards can yield negative shares or shares above 100%; the chart does not clip them. Any missing air yards among a team's identified targets, or a nonpositive team total, makes that team's air-yard shares unavailable. The table retains these rows while the scatter omits them with an annotation. This is descriptive research, not a model input or a prediction.

Provider semantics: [nflfastR field definitions](https://nflfastr.com/articles/field_descriptions.html) and [play-type changes for two-point attempts](https://nflfastr.com/news/).

## Team matchup context

`TeamMatchups` computes dropback EPA (including sacks and scrambles), designed-rush EPA (excluding dropbacks), and sacks per dropback from one season/cutoff snapshot. Kneels, spikes, nullified plays, two-point attempts and postseason plays are excluded. Missing metric outcomes are excluded from their denominator; both observed and eligible play counts remain in the table and tooltip. Rates are play-weighted, not unweighted averages of game means.

`team_matchup` draws one metric at a time so EPA and sack percentages never share an axis. EPA is from the offense perspective; defensive EPA represents EPA allowed. Sack labels distinguish conceded versus made. The chart includes zero and does not convert raw metrics into inverted league rankings. These comparisons are descriptive and not opponent-adjusted forecasts or defense fantasy scoring.

## Neutral team tendencies

`NeutralTendencies` defines neutral plays as first/second downs, more than 120 half-seconds remaining, and offense win probability in [0.2, 0.8]. The denominator comprises qualifying observed dropbacks and designed rushes. Scrambles count with dropbacks. Kneels, spikes, two-point attempts, postseason and nullified plays are excluded. Missing context is counted separately; no qualifying sample yields an unknown rate. The chart uses a fixed 0-100% scale and includes sample counts in hover. This historical filter is not a calibrated forecast feature or a significance threshold.
