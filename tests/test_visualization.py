import pandas as pd
from fantasyfootball.visualization import PlotlyVisualizer
from fantasyfootball.cli import main
from fantasyfootball.application import DraftApplication
from fantasyfootball.domain import LeagueSettings


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
