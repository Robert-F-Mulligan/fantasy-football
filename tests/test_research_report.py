from pathlib import Path

import pandas as pd
import pytest

from fantasyfootball.reports.research import ResearchReport, main


def snapshot(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data = pd.read_csv(root / "examples" / "team_matchups.csv")
    data["receiver_player_id"] = "r1"
    data["receiver_player_name"] = "<img src=x onerror=alert(1)>"
    data["air_yards"] = 10.0
    data["down"] = 1
    data["half_seconds_remaining"] = 300
    data["wp"] = 0.5
    source = tmp_path / "source.csv"
    data.to_csv(source, index=False)
    return source


def test_report_is_offline_deterministic_and_contains_data_alternatives(tmp_path):
    source = snapshot(tmp_path)
    writer = ResearchReport()
    kwargs = {"season": 2026, "through_week": 1, "offense": "A", "defense": "B"}
    first = writer.write(source, tmp_path / "a.html", **kwargs).read_text(
        encoding="utf-8"
    )
    second = writer.write(source, tmp_path / "b.html", **kwargs).read_text(
        encoding="utf-8"
    )
    assert first == second
    assert first.count('class="plotly-graph-div"') == 5
    assert "<script src=" not in first
    assert "<img src=x" not in first and "&lt;img src=x" in first
    for anchor in ["receivers-data", "matchup-data", "tendencies-data"]:
        assert f'id="{anchor}"' in first
    assert "SHA-256:" in first and 'lang="en"' in first


def test_report_rejects_source_overwrite_and_invalid_matchup_before_writing(tmp_path):
    source = snapshot(tmp_path)
    before = source.read_bytes()
    writer = ResearchReport()
    with pytest.raises(ValueError, match="overwrite"):
        writer.write(
            source, source, season=2026, through_week=1, offense="A", defense="B"
        )
    output = tmp_path / "report.html"
    output.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="Both"):
        writer.write(
            source, output, season=2026, through_week=1, offense="MISSING", defense="B"
        )
    assert output.read_text() == "existing"
    assert source.read_bytes() == before


def test_cli_creates_report(tmp_path):
    source = snapshot(tmp_path)
    output = tmp_path / "report.html"
    main(
        [
            str(source),
            "--output",
            str(output),
            "--season",
            "2026",
            "--through-week",
            "1",
            "--offense",
            "A",
            "--defense",
            "B",
        ]
    )
    assert output.exists()
