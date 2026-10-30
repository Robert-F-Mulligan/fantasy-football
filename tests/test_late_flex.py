import pandas as pd

from fantasyfootball.lineups.optimization import LineupOptimizer
from fantasyfootball.lineups.weekly import WeeklyLineupPlanner


def players():
    return pd.DataFrame(
        {
            "player_id": ["late", "early", "bench"],
            "player_name": ["Late", "Early", "Bench"],
            "pos": ["RB", "RB", "WR"],
            "projected_points": [20.0, 10.0, 1.0],
            "kickoff": [
                "2026-11-02T01:00:00Z",
                "2026-11-01T18:00:00Z",
                "2026-11-03T01:00:00Z",
            ],
        }
    )


SLOTS = {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]}


def test_later_player_in_flex_without_changing_points_or_membership():
    board = players()
    original = LineupOptimizer().optimize(board, SLOTS)
    result = LineupOptimizer().optimize(board, SLOTS, prefer_late_flex=True)
    assert result.set_index("slot").player_id.to_dict() == {
        "RB1": "early",
        "FLEX1": "late",
    }
    assert set(result.player_id) == set(original.player_id)
    assert result.projected_points.sum() == original.projected_points.sum() == 30
    assert "bench" not in set(result.player_id)


def test_locked_flex_stays_even_when_it_starts_earlier():
    result = LineupOptimizer().optimize(
        players(), SLOTS, fixed_slots={"FLEX1": "early"}, prefer_late_flex=True
    )
    assert result.set_index("slot").loc["FLEX1", "player_id"] == "early"


def test_missing_or_equal_kickoffs_keep_the_original_assignment():
    for times in [[None, "2026-11-01", "2026-11-03"], ["2026-11-01"] * 3]:
        board = players().assign(kickoff=times)
        original = LineupOptimizer().optimize(board, SLOTS)
        result = LineupOptimizer().optimize(board, SLOTS, prefer_late_flex=True)
        pd.testing.assert_frame_equal(result, original)


def test_custom_slot_eligibility_and_superflex_are_respected():
    board = players()
    board["pos"] = ["QB", "QB", "RB"]
    board.loc[2, "projected_points"] = 5
    slots = {"QB1": ["QB"], "AnyOffense": ["QB", "RB", "WR", "TE"]}
    result = LineupOptimizer().optimize(board, slots, prefer_late_flex=True)
    assert result.set_index("slot").loc["AnyOffense", "player_id"] == "late"
    restricted = {"QB1": ["QB"], "Flex": ["RB", "WR", "TE"]}
    result = LineupOptimizer().optimize(board, restricted, prefer_late_flex=True)
    assert result.set_index("slot").loc["Flex", "pos"] == "RB"


def test_weekly_planner_enables_late_flex_and_retains_lock_rules():
    board = players()
    availability = board.drop(columns="projected_points").assign(
        availability="eligible", locked_slot=""
    )
    result = WeeklyLineupPlanner().recommend(
        board[["player_id", "projected_points"]], availability, SLOTS
    )
    assert result.set_index("slot").loc["FLEX1", "player_id"] == "late"
    availability.loc[1, ["availability", "locked_slot"]] = ["locked_starter", "FLEX1"]
    result = WeeklyLineupPlanner().recommend(
        board[["player_id", "projected_points"]], availability, SLOTS
    )
    assert result.set_index("slot").loc["FLEX1", "player_id"] == "early"


def test_multiple_flex_slots_and_equivalent_position_slots():
    board = players()
    more = board.iloc[[0]].assign(
        player_id="latest",
        player_name="Latest",
        kickoff="2026-11-03T02:00:00Z",
        projected_points=15.0,
    )
    board = pd.concat([board, more], ignore_index=True)
    slots = {
        "RB1": ["RB"],
        "RB2": ["RB"],
        "FlexA": ["RB", "WR", "TE"],
        "FlexB": ["RB", "WR", "TE"],
    }
    result = LineupOptimizer().optimize(board, slots, prefer_late_flex=True)
    assert set(result.loc[result.slot.isin(["FlexA", "FlexB"]), "player_id"]) == {
        "latest",
        "bench",
    }
    assert result.projected_points.sum() == board.projected_points.sum()
