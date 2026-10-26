"""Plotly chart adapter. Methods return figures and never open a browser."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
import plotly.express as px
from fantasyfootball.core.domain import numeric


@dataclass(frozen=True)
class ChartTheme:
    background: str = "#0b1220"
    panel: str = "#111d30"
    foreground: str = "#e6edf7"
    accent: str = "#55ddbb"


class PlotlyVisualizer:
    COLORS = {
        "QB": "#b697ff",
        "RB": "#55ddbb",
        "WR": "#69baff",
        "TE": "#ffc86b",
        "K": "#f391c1",
        "DST": "#a6b5ca",
    }

    def __init__(self, theme=None):
        self.theme = theme or ChartTheme()

    def _style(self, figure, title):
        figure.update_layout(
            title=title,
            template="plotly_dark",
            paper_bgcolor=self.theme.background,
            plot_bgcolor=self.theme.panel,
            font=dict(color=self.theme.foreground, family="Arial"),
            margin=dict(l=50, r=30, t=70, b=50),
            height=530,
            legend_title_text="Position",
        )
        return figure

    def draft_value(self, board):
        data = board.dropna(subset=["adp"]).copy()
        data["player_name"] = data.player_name.map(escape)
        figure = px.scatter(
            data,
            x="adp",
            y="value_over_replacement",
            color="pos",
            hover_name="player_name",
            color_discrete_map=self.COLORS,
            hover_data=["projected_points", "tier", "value_rank"],
            labels={
                "adp": "Average draft position",
                "value_over_replacement": "Points above replacement",
            },
        )
        figure.update_traces(marker=dict(size=10, opacity=0.85))
        figure.add_hline(y=0, line_dash="dot", line_color="#63758c")
        if data.empty:
            figure.add_annotation(
                text="No ADP supplied. Add ADP to compare market cost.",
                showarrow=False,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
            )
        return self._style(figure, "Market cost vs. draft value")

    def tiers(self, board, top=40):
        if top < 1:
            raise ValueError("top must be positive")
        data = board.head(top).iloc[::-1].copy()
        data["label"] = (
            data.player_name.map(escape)
            + " ("
            + data.pos
            + ") ["
            + data.player_id.map(escape)
            + "]"
        )
        figure = px.bar(
            data,
            x="projected_points",
            y="label",
            color="pos",
            orientation="h",
            color_discrete_map=self.COLORS,
            text="tier",
            hover_data=["value_over_replacement"],
            labels={"label": "", "projected_points": "Projected season points"},
        )
        self._style(figure, "Top available players · labels show positional tier")
        figure.update_layout(height=max(500, len(data) * 27))
        return figure

    def weekly_trends(self, weekly):
        data = numeric(weekly, ["week", "fantasy_points"]).sort_values("week")
        if not {"player_id", "player_name"}.issubset(data):
            raise ValueError("Weekly data needs player_id and player_name")
        if "season" in data and data.season.nunique() > 1:
            raise ValueError("Filter weekly trends to one season")
        if data.duplicated(["player_id", "week"]).any():
            raise ValueError("Weekly data must have one row per player and week")
        data = data.copy()
        data["player"] = (
            data.player_name.map(escape)
            + " ["
            + data.player_id.astype(str).map(escape)
            + "]"
        )
        return self._style(
            px.line(data, x="week", y="fantasy_points", color="player", markers=True),
            "Weekly fantasy production",
        )

    def write_report(self, board, destination, title="Fantasy draft lab"):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        figures = [self.draft_value(board), self.tiers(board)]
        fragments = [
            fig.to_html(
                full_html=False,
                include_plotlyjs=(i == 0),
                config={"responsive": True, "displaylogo": False},
            )
            for i, fig in enumerate(figures)
        ]
        columns = [
            "value_rank",
            "player_name",
            "pos",
            "tier",
            "projected_points",
            "value_over_replacement",
            "adp",
            "available_next_pick",
        ]
        table = board[columns].to_html(
            index=False,
            escape=True,
            float_format=lambda n: f"{n:.2f}",
            na_rep="Unknown",
        )
        content = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        content += f"<title>{escape(title)}</title><style>body{{margin:0;background:#0b1220;color:#e6edf7;font:16px Arial}}main{{max-width:1300px;margin:auto;padding:32px}}h1{{font-size:36px}}p{{color:#a6b5ca;line-height:1.6}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #26374d}}th{{color:#55ddbb}}</style></head><body><main>"
        content += f"<p>DRAFT RESEARCH / VALUE BOARD</p><h1>{escape(title)}</h1><p>{len(board)} available players · Hover to inspect, click legend positions to filter, drag to zoom. Rankings use points above league-specific replacement.</p>"
        content += "".join(fragments)
        content += "<h2>Available draft board</h2><p>Availability is a conditional normal-ADP heuristic (0–1), not a calibrated probability. Unknown means ADP or its dispersion is missing. Projections are estimates, not guarantees.</p>"
        content += '<div class="table">' + table + "</div></main></body></html>"
        path.write_text(content, encoding="utf-8")
        return path
