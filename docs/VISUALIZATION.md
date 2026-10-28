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
