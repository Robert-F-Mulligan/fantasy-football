"""Plotly chart adapter. Methods return figures and never open a browser."""

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import ClassVar

import pandas as pd
import plotly.express as px

from fantasyfootball.core.domain import numeric, players


@dataclass(frozen=True)
class ChartTheme:
    background: str = "#0b1220"
    panel: str = "#111d30"
    foreground: str = "#e6edf7"
    accent: str = "#55ddbb"


class PlotlyVisualizer:
    COLORS: ClassVar[dict[str, str]] = {
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
            font={"color": self.theme.foreground, "family": "Arial"},
            margin={"l": 50, "r": 30, "t": 70, "b": 50},
            height=530,
            legend_title_text="Position",
        )
        return figure

    def _board(self, board):
        data = numeric(
            players(board),
            ["projected_points", "value_over_replacement", "value_rank", "tier"],
        )
        if data.player_id.duplicated().any():
            raise ValueError("Draft charts require unique player_id values")
        if "adp" not in data:
            raise ValueError("Missing columns: adp")
        present = data.adp.notna()
        data.loc[present, "adp"] = numeric(data.loc[present], ["adp"]).adp
        if (data.loc[present, "adp"] <= 0).any():
            raise ValueError("adp must be positive when supplied")
        return data.sort_values(["value_rank", "player_id"], kind="stable")

    def draft_value(self, board):
        data = self._board(board).dropna(subset=["adp"]).copy()
        data["player_name"] = data.player_name.map(escape)
        figure = px.scatter(
            data,
            x="adp",
            y="value_over_replacement",
            color="pos",
            symbol="pos",
            category_orders={"pos": list(self.COLORS)},
            hover_name="player_name",
            color_discrete_map=self.COLORS,
            hover_data=["projected_points", "tier", "value_rank"],
            labels={
                "adp": "Average draft position",
                "value_over_replacement": "Points above replacement",
            },
        )
        figure.update_traces(marker={"size": 10, "opacity": 0.85})
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
        data = self._board(board).head(top).iloc[::-1].copy()
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
        figure.update_yaxes(categoryorder="array", categoryarray=data.label.tolist())
        figure.update_xaxes(rangemode="tozero")
        return figure

    @staticmethod
    def _weekly(weekly):
        data = numeric(weekly, ["week", "fantasy_points"]).sort_values("week")
        if not {"player_id", "player_name"}.issubset(data):
            raise ValueError("Weekly data needs player_id and player_name")
        if "season" in data and data.season.nunique() > 1:
            raise ValueError("Filter weekly trends to one season")
        if data.duplicated(["player_id", "week"]).any():
            raise ValueError("Weekly data must have one row per player and week")
        if data.week.lt(1).any() or data.week.mod(1).ne(0).any():
            raise ValueError("week must contain positive integers")
        if data[["player_id", "player_name"]].isna().any().any():
            raise ValueError("Player identifiers and names cannot be missing")
        data = data.copy()
        data["player_id"] = data.player_id.astype(str)
        data["player_name"] = data.player_name.astype(str)
        if data.duplicated(["player_id", "week"]).any():
            raise ValueError("Weekly data must have one row per player and week")
        return data

    def weekly_distribution(self, weekly):
        """Empirical cumulative frequency of observed games, not a forecast."""
        data = self._weekly(weekly)
        rows = []
        for pid, group in data.groupby("player_id", sort=True):
            label = escape(str(group.player_name.iloc[0])) + " [" + escape(pid) + "]"
            counts = group.fantasy_points.value_counts().sort_index()
            total = len(group)
            cumulative = 0
            for points, count in counts.items():
                if cumulative == 0:
                    rows.append((label, points, 0.0, total))
                cumulative += count
                rows.append((label, points, cumulative / total, total))
        plotted = pd.DataFrame(
            rows, columns=["player", "fantasy_points", "fraction", "games"]
        )
        figure = px.line(
            plotted,
            x="fantasy_points",
            y="fraction",
            color="player",
            line_dash="player",
            line_shape="hv",
            markers=True,
            hover_data=["games"],
            labels={
                "fantasy_points": "Observed fantasy points",
                "fraction": "Fraction of observed games at or below",
                "player": "Player",
            },
        )
        self._style(figure, "Historical game distribution (not a forecast)")
        figure.update_yaxes(range=[0, 1], tickformat=".0%")
        figure.update_layout(legend_title_text="Player")
        return figure

    def weekly_trends(self, weekly):
        data = self._weekly(weekly)
        # Explicit missing weeks break lines; absence is not zero production.
        groups = []
        for _, group in data.groupby("player_id", sort=True):
            expanded = group.set_index("week").reindex(
                range(int(group.week.min()), int(group.week.max()) + 1)
            )
            expanded["player_id"] = group.player_id.iloc[0]
            expanded["player_name"] = group.player_name.iloc[0]
            groups.append(expanded.rename_axis("week").reset_index())
        if groups:
            data = pd.concat(groups, ignore_index=True)
        data["player"] = (
            data.player_name.map(escape)
            + " ["
            + data.player_id.astype(str).map(escape)
            + "]"
        )
        figure = self._style(
            px.line(
                data,
                x="week",
                y="fantasy_points",
                color="player",
                line_dash="player",
                markers=True,
                labels={
                    "week": "NFL week",
                    "fantasy_points": "Fantasy points",
                    "player": "Player",
                },
            ),
            "Weekly fantasy production",
        )
        figure.update_traces(connectgaps=False)
        figure.update_xaxes(dtick=1)
        figure.update_layout(legend_title_text="Player")
        return figure

    def write_weekly_report(self, weekly, destination):
        """Export observed weekly research with numeric text alternatives."""
        data = self._weekly(weekly).sort_values(["player_id", "week"])
        figures = [self.weekly_trends(data), self.weekly_distribution(data)]
        descriptions = [
            "Observed weekly points; missing weeks break the lines.",
            "Fraction of observed games at or below each score. This is historical frequency, not a forecast or prediction interval.",
        ]
        document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Historical weekly research</title></head><body><h1>Historical weekly research</h1>'
        for index, (figure, description) in enumerate(zip(figures, descriptions)):
            document += f'<section aria-labelledby="weekly-heading-{index}"><h2 id="weekly-heading-{index}">{escape(figure.layout.title.text)}</h2><p>{description} <a href="#observations">Read the observations</a>.</p>'
            document += (
                figure.to_html(
                    full_html=False,
                    include_plotlyjs=(index == 0),
                    div_id=f"weekly-chart-{index}",
                    config={"responsive": True, "displaylogo": False},
                )
                + "</section>"
            )
        document += (
            '<h2 id="observations">Underlying observations</h2>'
            + data.to_html(index=False, escape=True)
            + "</body></html>"
        )
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document, encoding="utf-8")
        return path

    def write_report(self, board, destination, title="Fantasy draft lab"):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        board = self._board(board)
        figures = [self.draft_value(board), self.tiers(board)]
        fragments = [
            fig.to_html(
                full_html=False,
                div_id=f"draft-chart-{i}",
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
        content = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        content += f"<title>{escape(title)}</title><style>body{{margin:0;background:#0b1220;color:#e6edf7;font:16px Arial}}main{{max-width:1300px;margin:auto;padding:32px}}h1{{font-size:36px}}p{{color:#a6b5ca;line-height:1.6}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:12px;text-align:left;border-bottom:1px solid #26374d}}th{{color:#55ddbb}}</style></head><body><main>"
        content += f"<p>DRAFT RESEARCH / VALUE BOARD</p><h1>{escape(title)}</h1><p>{len(board)} available players · Hover to inspect, click legend positions to filter, drag to zoom. Rankings use points above league-specific replacement.</p>"
        descriptions = [
            "Market cost versus points above replacement. Symbols and colors identify positions. Players without ADP are omitted from this chart only.",
            "Top players ordered by value rank, best at the top. Bar length shows projected season points; labels show positional tier.",
        ]
        for i, (fragment, description) in enumerate(zip(fragments, descriptions)):
            content += f'<section aria-labelledby="chart-heading-{i}"><h2 id="chart-heading-{i}">{escape(figures[i].layout.title.text)}</h2><p>{description} <a href="#draft-data">Read the data table</a>.</p>{fragment}</section>'
        content += "<h2 id='draft-data'>Available draft board</h2><p>Availability is a conditional normal-ADP heuristic (0–1), not a calibrated probability. Unknown means ADP or its dispersion is missing. Projections are estimates, not guarantees.</p>"
        content += '<div class="table">' + table + "</div></main></body></html>"
        path.write_text(content, encoding="utf-8")
        return path
