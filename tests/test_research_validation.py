import json
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

from fantasyfootball.research.validate import main, validate_snapshot


def snapshot(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data = pd.read_csv(root / "examples" / "team_matchups.csv")
    data["receiver_player_id"] = "r1"
    data["receiver_player_name"] = "Receiver"
    data["air_yards"] = 10.0
    data["down"] = 1
    data["half_seconds_remaining"] = 300
    data["wp"] = 0.5
    path = tmp_path / "plays.csv"
    data.to_csv(path, index=False)
    return path


def test_snapshot_validation_checks_checksum_and_serializes_charts(tmp_path):
    path = snapshot(tmp_path)
    checksum = sha256(path.read_bytes()).hexdigest()
    result = validate_snapshot(
        path, season=2026, through_week=1, expected_sha256=checksum, charts=True
    )
    assert result["status"] == "passed"
    assert result["charts_serialized"] is True
    assert result["receiver_audit"]["identified_targets"] == 2
    with pytest.raises(ValueError, match="checksum"):
        validate_snapshot(path, season=2026, through_week=1, expected_sha256="wrong")


def test_cli_preserves_source_and_writes_report(tmp_path):
    path = snapshot(tmp_path)
    original = path.read_bytes()
    destination = tmp_path / "results" / "report.json"
    main(
        [
            str(path),
            "--season",
            "2026",
            "--through-week",
            "1",
            "--output",
            str(destination),
        ]
    )
    assert path.read_bytes() == original
    assert json.loads(destination.read_text())["status"] == "passed"
    with pytest.raises(SystemExit):
        main(
            [
                str(path),
                "--season",
                "2026",
                "--through-week",
                "1",
                "--output",
                str(path),
            ]
        )
    assert path.read_bytes() == original


def test_empty_requested_season_fails(tmp_path):
    with pytest.raises(ValueError, match="lacks observations"):
        validate_snapshot(snapshot(tmp_path), season=2025, through_week=1)
