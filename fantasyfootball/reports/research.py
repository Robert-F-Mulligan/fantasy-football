"""Self-contained historical research report; no network or email side effects."""

import argparse
from html import escape
from pathlib import Path

from fantasyfootball.research.matchups import TeamMatchups
from fantasyfootball.research.validate import analyze_snapshot


class ResearchReport:
    def write(
        self,
        source,
        destination,
        *,
        season,
        through_week,
        offense,
        defense,
        expected_sha256=None,
    ):
        source, destination = Path(source), Path(destination)
        if source.resolve() == destination.resolve():
            raise ValueError("Report must not overwrite the source snapshot")
        metadata, usage, matchups, tendencies = analyze_snapshot(
            source,
            season=season,
            through_week=through_week,
            expected_sha256=expected_sha256,
        )
        comparison = TeamMatchups().compare(matchups, offense=offense, defense=defense)
        # Plotly stays optional for data ingestion and hosted email workflows.
        from fantasyfootball.reports.visualization import PlotlyVisualizer

        visualizer = PlotlyVisualizer()
        sections = [
            (
                "receivers",
                "Receiver usage",
                "Shares use identified receiver targets within each team stint. Signed air-yard shares may exceed 100% or be negative. Unknown shares remain in the table.",
                [visualizer.receiver_usage(usage)],
                usage,
            ),
            (
                "matchup",
                "Selected matchup",
                "Historical offense produced versus defense allowed, using one snapshot. Separate axes retain each metric's units. These are not opponent-adjusted game forecasts.",
                [
                    visualizer.team_matchup(comparison, metric)
                    for metric in TeamMatchups.METRICS
                ],
                comparison,
            ),
            (
                "tendencies",
                "Neutral tendencies",
                "First/second downs, more than 120 half-seconds remaining, and offense win probability of 20-80%. Dropbacks include sacks and scrambles. Missing context is counted separately.",
                [visualizer.neutral_tendencies(tendencies)],
                tendencies,
            ),
        ]
        document = [
            '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Historical football research</title><style>body{margin:0;background:#0b1220;color:#e6edf7;font:16px Arial;line-height:1.5}main{max-width:1200px;margin:auto;padding:24px}a{color:#69baff}section{margin:32px 0}.data{overflow:auto}table{border-collapse:collapse;font-size:14px;width:100%}th,td{padding:8px;border-bottom:1px solid #63758c;text-align:left}code{overflow-wrap:anywhere}a:focus-visible{outline:3px solid #ffc86b}</style></head><body><main><h1>Historical football research</h1>'
        ]
        document.append(
            f"<p>{season}, through week {through_week}. Selected matchup: {escape(offense)} offense / {escape(defense)} defense.</p>"
        )
        document.append(
            '<nav aria-label="Report sections">'
            + " | ".join(
                f'<a href="#{key}">{heading}</a>' for key, heading, *_ in sections
            )
            + "</nav>"
        )
        document.append(
            f"<p>Source: {escape(metadata['source_name'])}<br>SHA-256: <code>{metadata['sha256']}</code></p>"
        )
        audit = metadata["receiver_audit"]
        document.append(
            f"<p>Coverage: {audit['identified_targets']:,} identified targets; {audit['unidentified_pass_plays']:,} pass plays without an identified receiver (may include sacks/throwaways); {metadata['unknown_air_yard_shares']} unknown air-yard shares; {metadata['incomplete_neutral_context']} eligible plays with incomplete neutral context.</p>"
        )
        chart_index = 0
        for key, heading, description, figures, table in sections:
            document.append(
                f'<section aria-labelledby="{key}"><h2 id="{key}">{heading}</h2><p>{description} <a href="#{key}-data">Read the data table</a>.</p>'
            )
            for figure in figures:
                document.append(
                    figure.to_html(
                        full_html=False,
                        include_plotlyjs=(chart_index == 0),
                        div_id=f"research-chart-{chart_index}",
                        config={"responsive": True, "displaylogo": False},
                    )
                )
                chart_index += 1
            document.append(
                f'<h3 id="{key}-data">{heading} data</h3><div class="data" role="region" aria-label="{heading} data table" tabindex="0">'
            )
            document.append(
                table.to_html(
                    index=False,
                    escape=True,
                    na_rep="Unknown",
                    float_format=lambda value: f"{value:.4f}",
                )
            )
            document.append("</div></section>")
        document.append(
            "<p>Descriptive research only. Unknown values are not zero; sample sizes refer to observed data. Data tables retain rows omitted from charts. No production forecast adjustments are made.</p></main></body></html>"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("".join(document), encoding="utf-8")
        return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int, required=True)
    parser.add_argument("--offense", required=True)
    parser.add_argument("--defense", required=True)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    result = ResearchReport().write(
        args.source,
        args.output,
        season=args.season,
        through_week=args.through_week,
        offense=args.offense,
        defense=args.defense,
        expected_sha256=args.expected_sha256,
    )
    print("Research report written:", result)


if __name__ == "__main__":
    main()
