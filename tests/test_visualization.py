import pandas as pd

from fantasyfootball.cli import main
from fantasyfootball.core.domain import LeagueSettings
from fantasyfootball.drafting.application import DraftApplication
from fantasyfootball.reports.visualization import PlotlyVisualizer


def sample():
    return pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "player_name": ["<script>alert(1)</script>", "B", "C"],
            "pos": ["QB"] * 3,
            "projected_points": [300, 200, 100],
        }
    )


def test_report_is_offline_and_escapes_names(tmp_path):
    board = DraftApplication(
        LeagueSettings(teams=1, starters={"QB": 1}, flex=0)
    ).prepare(sample())
    path = PlotlyVisualizer().write_report(board, tmp_path / "report.html")
    html = path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "plotly.js" in html
    assert "Unknown" in html
    assert len(PlotlyVisualizer().draft_value(board).layout.annotations) == 1


def test_cli_csv_and_report(tmp_path):
    import json

    data = tmp_path / "players.csv"
    sample().to_csv(data, index=False)
    config = tmp_path / "league.json"
    config.write_text(json.dumps({"teams": 1, "starters": {"QB": 1}, "flex": 0}))
    main(
        [
            "draft",
            str(data),
            "--league",
            str(config),
            "--output",
            str(tmp_path / "board.csv"),
            "--html",
            str(tmp_path / "report.html"),
        ]
    )
    assert len(pd.read_csv(tmp_path / "board.csv")) == 3
    assert (tmp_path / "report.html").is_file()


def draft_board():
    return DraftApplication(
        LeagueSettings(teams=1, starters={"QB": 1}, flex=0)
    ).prepare(sample())


def test_rank_order_does_not_depend_on_input_order():
    board = draft_board()
    figure = PlotlyVisualizer().tiers(board.iloc[::-1], top=2)
    labels = list(figure.layout.yaxis.categoryarray)
    assert labels[-1].endswith("[a]")
    assert labels[0].endswith("[b]")
    assert figure.layout.xaxis.rangemode == "tozero"


def test_report_export_is_deterministic_and_has_text_alternatives(tmp_path):
    chart = PlotlyVisualizer()
    a = chart.write_report(draft_board(), tmp_path / "a.html").read_bytes()
    b = chart.write_report(draft_board().iloc[::-1], tmp_path / "b.html").read_bytes()
    assert a == b
    assert b'lang="en"' in a
    assert b"Read the data table" in a
    assert b'aria-labelledby="chart-heading-0"' in a
    assert b'id="draft-chart-0"' in a


def test_invalid_numbers_and_duplicate_players_are_rejected():
    import pytest

    board = draft_board()
    for column in ["projected_points", "value_over_replacement", "adp"]:
        invalid = board.copy()
        invalid[column] = invalid[column].astype(float)
        invalid.loc[0, column] = float("inf")
        with pytest.raises(ValueError, match="finite"):
            PlotlyVisualizer().tiers(invalid)
    with pytest.raises(ValueError, match="unique"):
        PlotlyVisualizer().draft_value(pd.concat([board, board]))


def test_weekly_missing_observations_are_gaps_not_zero():
    weekly = pd.DataFrame(
        {
            "player_id": [1, 1],
            "player_name": ["A", "A"],
            "week": [1, 3],
            "fantasy_points": [10, 20],
        }
    )
    before = weekly.copy(deep=True)
    figure = PlotlyVisualizer().weekly_trends(weekly)
    trace = figure.data[0]
    assert list(trace.x) == [1, 2, 3]
    assert pd.isna(trace.y[1])
    assert trace.connectgaps is False
    assert figure.layout.legend.title.text == "Player"
    assert figure.layout.xaxis.dtick == 1
    pd.testing.assert_frame_equal(weekly, before)


def test_empirical_distribution_counts_ties_and_negative_points():
    data = pd.DataFrame(
        {
            "player_id": ["a"] * 3,
            "player_name": ["<unsafe>"] * 3,
            "season": [2026] * 3,
            "week": [1, 2, 4],
            "fantasy_points": [-1, 10, 10],
        }
    )
    figure = PlotlyVisualizer().weekly_distribution(data)
    assert list(figure.data[0].x) == [-1, -1, 10]
    assert list(figure.data[0].y) == [0, 1 / 3, 1]
    assert figure.data[0].line.shape == "hv"
    assert "<unsafe>" not in figure.data[0].name


def test_weekly_export_is_deterministic_and_escaped(tmp_path):
    data = pd.DataFrame(
        {
            "player_id": ["a", "a"],
            "player_name": ["<script>"] * 2,
            "week": [1, 3],
            "fantasy_points": [5.0, 10.0],
        }
    )
    chart = PlotlyVisualizer()
    a = chart.write_weekly_report(data, tmp_path / "one.html").read_bytes()
    b = chart.write_weekly_report(data.iloc[::-1], tmp_path / "two.html").read_bytes()
    assert a == b
    assert b"&lt;script&gt;" in a
    assert b"Underlying observations" in a and b"not a forecast" in a
