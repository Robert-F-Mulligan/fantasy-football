import pandas as pd
import pytest

from fantasyfootball.waivers.roles import SleeperRoleContext


def player(**changes):
    return {
        "position": "QB",
        "depth_chart_position": "QB",
        "depth_chart_order": 1,
        "team": "LA",
        "status": "Active",
        **changes,
    }


def test_first_listing_never_claims_a_confirmed_starter():
    state, order, note = SleeperRoleContext({"1": player()}).describe("1", "QB")
    assert (state, order) == ("listed", 1)
    assert note == "Sleeper depth: QB1"


def test_backup_qb_is_flagged_without_changing_projection():
    frame = pd.DataFrame([{"sleeper_id": "1", "pos": "QB", "projected_points": 22.5}])
    result = SleeperRoleContext({"1": player(depth_chart_order=2)}).annotate(frame)
    assert result.projected_points.tolist() == [22.5]
    assert "weak opportunity forecast" in result.role_note.item()
    assert "role_status" not in frame


@pytest.mark.parametrize(
    "value", [None, True, 0, -1, 1.5, "1", float("nan"), float("inf")]
)
def test_invalid_depth_is_unknown(value):
    assert SleeperRoleContext({"1": player(depth_chart_order=value)}).describe(
        "1", "QB"
    )[:2] == ("unknown", None)


def test_conflicting_active_entries_and_rams_alias():
    context = SleeperRoleContext({"1": player(), "2": player(team="LAR")})
    assert context.describe("1", "QB")[0] == "conflict"
    context = SleeperRoleContext({"1": player(), "2": player(status="Inactive")})
    assert context.describe("1", "QB")[0] == "listed"


def test_position_mismatch_missing_player_and_specialists():
    context = SleeperRoleContext({"1": player(depth_chart_position="RB")})
    assert context.describe("1", "QB")[0] == "unknown"
    assert context.describe("missing", "QB")[0] == "unknown"
    assert context.describe("1", "DEF")[0] == "not_applicable"
    context = SleeperRoleContext({"1": player()})
    assert context.describe("1", "WR")[0] == "unknown"


def test_empty_frame_and_receiver_depth_not_treated_as_qb_backup():
    context = SleeperRoleContext(
        {"1": player(position="WR", depth_chart_position="WR", depth_chart_order=3)}
    )
    assert "backup" not in context.describe("1", "WR")[2]
    assert context.annotate(pd.DataFrame(columns=["sleeper_id", "pos"])).empty


def test_workload_flag_excludes_future_and_missing_usage():
    from fantasyfootball.waivers.roles import workload_notes

    history = pd.DataFrame(
        {
            "player_id": ["a"] * 4,
            "pos": ["WR"] * 4,
            "season": [2026] * 4,
            "week": [1, 2, 3, 4],
            "rushing_att": [0.0, 0.0, 0.0, 100.0],
            "receiving_tgt": [1.0, 2.0, 3.0, 100.0],
        }
    )
    assert "2.0 carries + targets/game over 3" in workload_notes(history, 2026, 4)["a"]
    assert not workload_notes(history, 2026, 1)
    history.loc[1, "receiving_tgt"] = float("nan")
    assert not workload_notes(history, 2026, 4)
