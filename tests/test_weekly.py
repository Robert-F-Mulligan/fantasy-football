import pandas as pd
import pytest

from fantasyfootball.lineups.optimization import LineupOptimizer
from fantasyfootball.lineups.weekly import WeeklyLineupPlanner


def fixture():
    roster = pd.DataFrame(
        [
            {
                "sleeper_id": "1",
                "player_id": "a",
                "player_name": "A",
                "pos": "RB",
                "starter_slot": "FLEX1",
                "is_reserve": False,
                "is_taxi": False,
            },
            {
                "sleeper_id": "2",
                "player_id": "b",
                "player_name": "B",
                "pos": "RB",
                "starter_slot": "",
                "is_reserve": False,
                "is_taxi": False,
            },
            {
                "sleeper_id": "3",
                "player_id": "c",
                "player_name": "C",
                "pos": "WR",
                "starter_slot": "",
                "is_reserve": False,
                "is_taxi": False,
            },
        ]
    )
    details = {
        str(i): {"team": team, "status": "Active", "injury_status": None}
        for i, team in [(1, "NE"), (2, "NE"), (3, "NYJ")]
    }
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 7,
                "game_type": "REG",
                "game_id": "one",
                "home_team": "CHI",
                "away_team": "NE",
                "gameday": "2026-10-22",
                "gametime": "20:15",
            },
            {
                "season": 2026,
                "week": 7,
                "game_type": "REG",
                "game_id": "two",
                "home_team": "NYJ",
                "away_team": "MIA",
                "gameday": "2026-10-25",
                "gametime": "13:00",
            },
        ]
    )
    return roster, details, schedule


def available(roster, details, schedule, as_of="2026-10-24T12:00:00-04:00"):
    return WeeklyLineupPlanner().availability(
        roster, details, schedule, season=2026, week=7, as_of=as_of
    )


def test_kickoff_locks_starter_exact_slot_and_excludes_bench():
    roster, details, schedule = fixture()
    audit = available(roster, details, schedule)
    assert audit.availability.tolist() == ["locked_starter", "locked_bench", "eligible"]
    assert audit.kickoff.iloc[0] == pd.Timestamp("2026-10-23T00:15:00Z")
    projections = pd.DataFrame(
        {"player_id": ["a", "b", "c"], "projected_points": [1, 100, 10]}
    )
    result = WeeklyLineupPlanner().recommend(
        projections, audit, {"WR1": ["WR"], "FLEX1": ["WR", "RB"]}
    )
    assert result.set_index("slot").player_id.to_dict() == {"WR1": "c", "FLEX1": "a"}


def test_fixed_flex_cannot_be_moved_to_make_an_illegal_lineup():
    board = pd.DataFrame(
        {
            "player_id": ["a", "c"],
            "player_name": ["A", "C"],
            "pos": ["RB", "WR"],
            "projected_points": [1, 20],
        }
    )
    with pytest.raises(ValueError, match="Cannot fill"):
        LineupOptimizer().optimize(
            board, {"RB1": ["RB"], "FLEX1": ["RB", "WR"]}, fixed_slots={"FLEX1": "a"}
        )


@pytest.mark.parametrize(
    "status,expected",
    [("Out", "unavailable"), ("Doubtful", "unavailable"), ("Questionable", "eligible")],
)
def test_injury_status_before_kickoff(status, expected):
    roster, details, schedule = fixture()
    details["3"]["injury_status"] = status
    audit = available(roster, details, schedule)
    assert audit.availability.iloc[2] == expected
    assert audit.injury_status.iloc[2] == status.casefold()
    assert audit.warning.iloc[2]


def test_unknown_team_blocks_recommendation():
    roster, details, schedule = fixture()
    details["3"]["team"] = None
    audit = available(roster, details, schedule)
    with pytest.raises(ValueError, match="unknown"):
        WeeklyLineupPlanner().recommend(pd.DataFrame(), audit, {"FLEX1": ["RB", "WR"]})


def test_no_scheduled_game_and_reserve_excluded():
    roster, details, schedule = fixture()
    schedule.loc[1, "week"] = 8
    assert (
        available(roster, details, schedule).availability.iloc[2] == "no_scheduled_game"
    )
    schedule.loc[1, "week"] = 7
    roster.loc[2, "is_reserve"] = True
    assert available(roster, details, schedule).availability.iloc[2] == "reserve"


@pytest.mark.parametrize(
    "kind", ["no_timezone", "missing_time", "duplicate_team", "empty_week"]
)
def test_ambiguous_schedule_rejected(kind):
    roster, details, schedule = fixture()
    now = "2026-10-24T12:00:00Z"
    if kind == "no_timezone":
        now = "2026-10-24T12:00:00"
    if kind == "missing_time":
        schedule.loc[0, "gametime"] = None
    if kind == "duplicate_team":
        schedule.loc[1, "home_team"] = "NE"
    if kind == "empty_week":
        schedule["week"] = 8
    with pytest.raises(ValueError):
        available(roster, details, schedule, now)


def test_kickoff_boundary_locks_and_no_projection_is_not_zero():
    roster, details, schedule = fixture()
    audit = available(roster, details, schedule, "2026-10-23T00:15:00Z")
    assert audit.availability.iloc[0] == "locked_starter"
    with pytest.raises(ValueError, match="needs a projection"):
        WeeklyLineupPlanner().recommend(
            pd.DataFrame({"player_id": ["a"], "projected_points": [1]}),
            audit,
            {"FLEX1": ["RB", "WR"]},
        )


def test_team_defense_is_explicitly_outside_offensive_scope():
    roster, details, schedule = fixture()
    roster.loc[2, "player_id"] = None
    roster.loc[2, "pos"] = None
    details["3"]["position"] = "DEF"
    audit = available(roster, details, schedule)
    assert audit.availability.iloc[2] == "unsupported_position"


def test_missing_player_position_does_not_silently_disappear():
    roster, details, schedule = fixture()
    roster.loc[2, "pos"] = None
    assert available(roster, details, schedule).availability.iloc[2] == "unknown"


def test_old_import_without_slot_information_is_rejected():
    roster, details, schedule = fixture()
    with pytest.raises(ValueError, match="Refresh"):
        available(roster.drop(columns="starter_slot"), details, schedule)
