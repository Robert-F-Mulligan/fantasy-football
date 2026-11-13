import json
import sys

import pandas as pd
import pytest

from fantasyfootball.evaluation.defense_investigation import investigate, main
from fantasyfootball.evaluation.defense_triage import DefenseDiscrepancyTriage


def inputs():
    source = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "team": "NE",
                "game_id": "g",
                "season_type": "REG",
                "def_fumbles_forced": 2,
            }
        ]
    )
    records = [
        {
            "season": "2026",
            "week": 1,
            "player_id": "NE",
            "player": {"position": "DEF"},
            "season_type": "regular",
            "category": "stat",
            "stats": {"ff": 1, "def_st_ff": 1},
        }
    ]
    return source, records


def test_arithmetic_clue_never_resolves_case_and_keeps_stable_id():
    source, records = inputs()
    reports, tables = investigate(
        source, {"ff": 1}, records, season=2026, through_week=1
    )
    case = tables["discrepancy-cases"].iloc[0]
    assert case.case_id == "2026-W01-NE-ff"
    assert case.hypothesis == "special_teams_ff_arithmetic_compatible"
    assert case.resolution_status == "unresolved"
    assert reports["triage"]["resolved_cases"] == 0
    assert reports["triage"]["ready_for_scoring"] is False
    records[0]["stats"].pop("def_st_ff")
    _, missing = DefenseDiscrepancyTriage().triage(
        tables["component-comparisons"], source, records
    )
    assert missing.hypothesis.iloc[0] == "unexplained"
    assert json.loads(missing.sleeper_context.iloc[0])["def_st_ff"] is None


def test_duplicate_context_is_rejected():
    source, records = inputs()
    _, tables = investigate(source, {"ff": 1}, records, season=2026, through_week=1)
    with pytest.raises(ValueError, match="Duplicate regular-season"):
        DefenseDiscrepancyTriage().triage(
            tables["component-comparisons"], pd.concat([source, source]), records
        )
    with pytest.raises(ValueError, match="Duplicate provider"):
        DefenseDiscrepancyTriage().triage(
            tables["component-comparisons"], source, records * 2
        )


def test_cli_hashes_and_overwrite_protection(tmp_path, monkeypatch):
    source, records = inputs()
    source.to_csv(tmp_path / "stats.csv", index=False)
    (tmp_path / "settings.json").write_text(
        json.dumps({"league_id": "private", "scoring_settings": {"ff": 1}})
    )
    (tmp_path / "provider.json").write_text(json.dumps(records))
    args = [
        "audit",
        "--team-stats",
        str(tmp_path / "stats.csv"),
        "--settings",
        str(tmp_path / "settings.json"),
        "--sleeper-stats",
        str(tmp_path / "provider.json"),
        "--season",
        "2026",
        "--through-week",
        "1",
        "--output",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr(sys, "argv", args)
    main()
    text = (tmp_path / "out" / "triage.json").read_text()
    assert "private" not in text and "league_id" not in text
    assert len(json.loads(text)["input_sha256"]["team_stats"]) == 64
    assert (tmp_path / "out" / "discrepancy-cases.csv").exists()
    with pytest.raises(FileExistsError):
        main()


def test_event_components_are_comparable_without_assuming_coverage():
    source, records = inputs()
    pbp = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "season_type": "REG",
                "game_id": "g",
                "play_id": 1,
                "home_team": "NE",
                "away_team": "BUF",
                "play_type": "run",
                "posteam": "BUF",
                "defteam": "NE",
                "down": 4,
                "fourth_down_failed": 1,
                "fourth_down_converted": 0,
                "penalty": 0,
                "fumble": 0,
                "touchdown": 0,
            }
        ]
    )
    records[0]["stats"]["def_4_and_stop"] = 1
    reports, tables = investigate(
        source, {"ff": 1}, records, season=2026, through_week=1, pbp=pbp
    )
    assert tables["event_components"].source_count.isna().all()
    assert reports["event_reconciliation"]["ready_for_scoring"] is False
    _, tables = investigate(
        source,
        {"ff": 1},
        records,
        season=2026,
        through_week=1,
        pbp=pbp,
        complete_game_ids=["g"],
    )
    match = tables["event_comparisons"].query(
        "team == 'NE' and scoring_key == 'def_4_and_stop'"
    )
    assert match.status.iloc[0] == "matched"
