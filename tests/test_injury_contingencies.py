import pandas as pd

from fantasyfootball.lineups.contingencies import injury_contingencies
from fantasyfootball.reports.lineup import render_contingencies

NOW = "2026-10-28T14:00:00Z"
SLOTS = {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]}


def fixture():
    board = pd.DataFrame(
        {
            "player_id": ["q", "r", "b", "early"],
            "player_name": ["Questionable", "Retained", "Backup", "Early"],
            "pos": ["RB", "RB", "WR", "RB"],
            "projected_points": [15.0, 12.0, 10.0, 20.0],
            "availability": ["eligible"] * 4,
            "injury_status": ["questionable", "", "", ""],
            "kickoff": [
                "2026-11-01T21:00:00Z",
                "2026-11-02T01:00:00Z",
                "2026-11-02T01:00:00Z",
                "2026-11-01T18:00:00Z",
            ],
        }
    )
    lineup = pd.DataFrame({"player_id": ["q", "r"], "slot": ["RB1", "FLEX1"]})
    return board, lineup


def test_prefers_late_fallback_and_reassigns_flex_legally():
    board, lineup = fixture()
    result = injury_contingencies(board, lineup, SLOTS, NOW)[0]
    assert result["option"]["player_id"] == "b"
    assert result["option"]["later"]
    assert result["option"]["assignments"] == [
        {"player_name": "Retained", "from_slot": "FLEX1", "slot": "RB1"},
        {"player_name": "Backup", "from_slot": None, "slot": "FLEX1"},
    ]


def test_started_or_earlier_retained_player_cannot_be_moved():
    for status, kickoff in [
        ("locked_starter", "2026-11-02T01:00:00Z"),
        ("eligible", "2026-11-01T18:00:00Z"),
    ]:
        board, lineup = fixture()
        board.loc[1, ["availability", "kickoff"]] = [status, kickoff]
        option = injury_contingencies(board, lineup, SLOTS, NOW)[0]["option"]
        assert option["player_id"] == "early"
        assert not option["later"]


def test_no_safe_option_when_bench_is_flagged_locked_or_missing_time():
    for field, value in [
        ("injury_status", "questionable"),
        ("availability", "locked_bench"),
        ("availability", "reserve"),
        ("kickoff", None),
        ("projected_points", float("nan")),
    ]:
        board, lineup = fixture()
        board.loc[2:, field] = value
        assert injury_contingencies(board, lineup, SLOTS, NOW)[0]["option"] is None


def test_exact_league_eligibility_not_flex_name_determines_options():
    board, lineup = fixture()
    slots = {"RB1": ["RB"], "FLEX1": ["TE"]}
    assert injury_contingencies(board, lineup, slots, NOW)[0]["option"] is None


def test_missing_audit_or_locked_questionable_starter_does_not_invent_plan():
    board, lineup = fixture()
    assert injury_contingencies(board, lineup, None, NOW) == []
    assert injury_contingencies(board, lineup, SLOTS, None) == []
    board.loc[0, "availability"] = "locked_starter"
    assert injury_contingencies(board, lineup, SLOTS, NOW) == []


def test_email_escapes_names_and_explains_early_deadline():
    board, lineup = fixture()
    board.loc[2, "availability"] = "unavailable"
    board.loc[3, "player_name"] = "<Early>"
    html, text = render_contingencies(board, lineup, SLOTS, NOW)
    assert "&lt;Early&gt;" in html and "<Early>" not in html
    for output in [html, text]:
        assert "Earlier decision required" in output
        assert "01:00 PM EST" in output
        assert "only that starter is out" in output


def test_equal_kickoff_backup_and_legacy_questionable_warning():
    board, lineup = fixture()
    board = board.drop(columns="injury_status")
    board["warning"] = [
        "Injury designation: questionable; recheck before kickoff",
        "",
        "",
        "",
    ]
    board.loc[3, "kickoff"] = board.loc[0, "kickoff"]
    option = injury_contingencies(board, lineup, SLOTS, NOW)[0]["option"]
    assert option["player_id"] == "early" and option["later"]


def test_report_reads_saved_slot_rules(tmp_path):
    import json

    from fantasyfootball.reports.reporting import render_report

    board, lineup = fixture()
    board["sleeper_id"] = board.player_id
    board["starter_slot"] = ["RB1", "FLEX1", "", ""]
    board["warning"] = ""
    board["opp"] = "NYJ"
    board.drop(columns="projected_points").to_csv(
        tmp_path / "availability.csv", index=False
    )
    board[["player_id", "projected_points"]].to_csv(
        tmp_path / "projections.csv", index=False
    )
    lineup.merge(board[["player_id", "projected_points"]], on="player_id").to_csv(
        tmp_path / "lineup.csv", index=False
    )
    (tmp_path / "plan-report.json").write_text(
        json.dumps(
            {
                "status": "offensive_lineup_created",
                "as_of": NOW,
                "offensive_slots": SLOTS,
                "history_cutoff": 202607,
                "unsupported_scoring": {},
            }
        ),
        encoding="utf-8",
    )
    _, plain, html = render_report(tmp_path, "Team", 2026, 8)
    for output in [plain, html]:
        assert "Injury backup plan" in output
        assert "Backup to FLEX1" in output
        assert output.index("Injury backup plan") < output.index("Recommended starters")


def multiple_injuries():
    board, lineup = fixture()
    board.loc[1, "injury_status"] = "questionable"
    board.loc[2, "pos"] = "RB"
    board.loc[3, "kickoff"] = "2026-11-02T01:00:00Z"
    return board, lineup


def test_combined_plan_uses_distinct_backups_for_each_opening():
    from fantasyfootball.lineups.contingencies import combined_injury_contingency

    board, lineup = multiple_injuries()
    individual = injury_contingencies(board, lineup, SLOTS, NOW)
    assert {r["option"]["player_id"] for r in individual} == {"early"}
    joint = combined_injury_contingency(board, lineup, SLOTS, NOW)
    assert joint["status"] == "ready"
    assert {r["player_id"] for r in joint["backups"]} == {"b", "early"}
    assert len(joint["assignments"]) == 2
    assert not joint["earlier"]


def test_individually_feasible_plans_do_not_imply_combined_coverage():
    from fantasyfootball.lineups.contingencies import combined_injury_contingency

    board, lineup = multiple_injuries()
    board.loc[2, "availability"] = "reserve"
    assert all(
        r["option"] is not None for r in injury_contingencies(board, lineup, SLOTS, NOW)
    )
    assert (
        combined_injury_contingency(board, lineup, SLOTS, NOW)["status"]
        == "unavailable"
    )
    html, text = render_contingencies(board, lineup, SLOTS, NOW)
    for output in [html, text]:
        assert "cannot fill every opening" in output
        assert "cannot all be used together" in output


def test_combined_plan_requires_earlier_decision_when_a_backup_plays_early():
    from fantasyfootball.lineups.contingencies import combined_injury_contingency

    board, lineup = multiple_injuries()
    board.loc[3, "kickoff"] = "2026-11-01T18:00:00Z"
    joint = combined_injury_contingency(board, lineup, SLOTS, NOW)
    assert joint["earlier"]
    assert joint["deadline"] == pd.Timestamp("2026-11-01T18:00:00Z")
    html, text = render_contingencies(board, lineup, SLOTS, NOW)
    for output in [html, text]:
        assert "Each backup is used once" in output
        assert "status may not be confirmed before its deadline" in output


def test_combined_plan_retains_locked_and_unaffected_starters():
    from fantasyfootball.lineups.contingencies import combined_injury_contingency

    board, lineup = multiple_injuries()
    extra = board.iloc[[0]].copy()
    extra["player_id"] = "locked"
    extra["player_name"] = "Locked"
    extra["injury_status"] = ""
    extra["availability"] = "locked_starter"
    extra["kickoff"] = "2026-10-27T18:00:00Z"
    board = pd.concat([board, extra], ignore_index=True)
    lineup = pd.concat(
        [lineup, pd.DataFrame({"player_id": ["locked"], "slot": ["RB2"]})],
        ignore_index=True,
    )
    slots = dict(SLOTS, RB2=["RB"])
    joint = combined_injury_contingency(board, lineup, slots, NOW)
    assert joint["status"] == "ready"
    assert all(r["slot"] != "RB2" for r in joint["assignments"])
    board.loc[2, "pos"] = "WR"
    board.loc[3, "pos"] = "WR"
    assert (
        combined_injury_contingency(board, lineup, slots, NOW)["status"]
        == "unavailable"
    )


def test_no_combined_plan_for_one_questionable_or_missing_snapshot():
    from fantasyfootball.lineups.contingencies import combined_injury_contingency

    board, lineup = fixture()
    assert combined_injury_contingency(board, lineup, SLOTS, NOW) is None
    board, lineup = multiple_injuries()
    assert combined_injury_contingency(board, lineup, SLOTS, None) is None
