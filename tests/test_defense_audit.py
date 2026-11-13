import json
import sys

import pandas as pd
import pytest

from fantasyfootball.evaluation.defense import DefenseScoringAudit, main


def stats():
    return pd.DataFrame(
        {
            "season": [2026, 2026, 2026],
            "week": [1, 2, 3],
            "team": ["NE"] * 3,
            "game_id": ["g1", "g2", "g3"],
            "season_type": ["REG"] * 3,
            "def_sacks": [3.0, 0.0, 4.0],
            "def_interceptions": [1.0, 0.0, 2.0],
            "def_punt_blocks": [1.0, 0.0, 0.0],
            "def_pat_blocks": [0.0, 0.0, 1.0],
            "def_fg_blocks": [1.0, 0.0, 0.0],
        }
    )


def test_audit_keeps_components_separate_and_never_claims_complete_scores():
    report, rows = DefenseScoringAudit().audit(
        stats(),
        {
            "sack": 1,
            "int": 2,
            "blk_kick": 2,
            "pts_allow_0": 10,
            "def_st_ff": 1,
            "st_ff": 1,
            "rec": 1,
            "xpm": 1,
        },
        season=2026,
        through_week=2,
    )
    assert report["team_games"] == 2
    assert not report["ready_for_scoring"]
    assert report["blocking_components"] == ["def_st_ff", "pts_allow_0"]
    assert set(report["ignored_individual_or_kicking_settings"]) == {
        "st_ff",
        "rec",
        "xpm",
    }
    assert (
        rows.loc[
            (rows.week == 1) & (rows.scoring_key == "blk_kick"),
            "candidate_component_points",
        ].iloc[0]
        == 4
    )
    assert rows.loc[rows.week == 2, "candidate_component_points"].eq(0).all()
    assert "projected_points" not in rows


@pytest.mark.parametrize("bad", [None, float("inf"), -1, "bad"])
def test_missing_and_invalid_counts_are_not_zero_filled(bad):
    data = stats()
    data["def_sacks"] = data.def_sacks.astype(object)
    data.loc[0, "def_sacks"] = bad
    report, rows = DefenseScoringAudit().audit(
        data, {"sack": 1}, season=2026, through_week=2
    )
    assert report["components"][0]["status"] == "invalid_values"
    assert report["components"][0]["valid_rows"] == 1
    assert pd.isna(rows.candidate_component_points.iloc[0])


def test_missing_component_and_unclassified_setting_block():
    report, _ = DefenseScoringAudit().audit(
        stats().drop(columns="def_fg_blocks"),
        {"blk_kick": 2, "new_def_rule": 1, "fum_rec": 2},
        season=2026,
        through_week=1,
    )
    assert set(report["blocking_components"]) == {"blk_kick", "new_def_rule", "fum_rec"}
    assert report["components"][0]["status"] == "missing_columns"


def test_duplicate_rows_nonfinite_weights_and_invalid_windows_fail():
    with pytest.raises(ValueError, match="Duplicate"):
        DefenseScoringAudit().audit(
            pd.concat([stats(), stats()]), {}, season=2026, through_week=2
        )
    with pytest.raises(ValueError, match="finite"):
        DefenseScoringAudit().audit(
            stats(), {"sack": float("nan")}, season=2026, through_week=2
        )
    with pytest.raises(ValueError, match="Through-week"):
        DefenseScoringAudit().audit(stats(), {}, season=2026, through_week=19)


def test_postseason_and_later_weeks_excluded():
    data = stats()
    data.loc[1, "season_type"] = "POST"
    report, rows = DefenseScoringAudit().audit(
        data, {"sack": 1}, season=2026, through_week=2
    )
    assert report["observed_weeks"] == [1]
    assert len(rows) == 1


@pytest.mark.parametrize("reconcile", [False, True])
def test_cli_records_hashes_without_league_metadata(tmp_path, monkeypatch, reconcile):
    source = tmp_path / "stats.csv"
    settings = tmp_path / "settings.json"
    output = tmp_path / "audit"
    stats().to_csv(source, index=False)
    settings.write_text(
        json.dumps({"league_id": "private", "scoring_settings": {"sack": 1}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit",
            "--team-stats",
            str(source),
            "--settings",
            str(settings),
            "--season",
            "2026",
            "--through-week",
            "2",
            "--output",
            str(output),
        ],
    )
    if reconcile:
        provider = tmp_path / "sleeper.json"
        provider.write_text(
            json.dumps(
                [
                    {
                        "season": "2026",
                        "week": 1,
                        "player_id": "NE",
                        "player": {"position": "DEF"},
                        "category": "stat",
                        "season_type": "regular",
                        "stats": {"sack": 3},
                    }
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(sys, "argv", sys.argv + ["--sleeper-stats", str(provider)])
    main()
    if reconcile:
        result = json.loads(
            (output / "reconciliation.json").read_text(encoding="utf-8")
        )
        assert result["components"][0]["matched_rows"] == 1
        assert len(result["input_sha256"]["sleeper_stats"]) == 64
    text = (output / "coverage.json").read_text(encoding="utf-8")
    assert "private" not in text and "league_id" not in text
    assert len(json.loads(text)["input_sha256"]["team_stats"]) == 64
    assert (output / "candidate-components.csv").exists()
    with pytest.raises(FileExistsError):
        main()
