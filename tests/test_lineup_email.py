import pandas as pd
import pytest

from fantasyfootball.reports.lineup import kickoff_label, render_lineup_brief


def roster():
    return pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "player_name": ["Alpha", "Bravo", "Charlie"],
            "pos": ["RB", "WR", "RB"],
            "starter_slot": ["RB1", "FLEX1", ""],
            "availability": ["eligible"] * 3,
            "projected_points": [12.0, 8.0, 15.0],
            "prediction_lower": [3.0, 2.0, 5.0],
            "prediction_upper": [20.0, 18.0, 22.0],
            "opp": ["NYJ"] * 3,
            "kickoff": ["2026-11-01T18:00:00Z"] * 3,
            "history_games": [10, 3, 10],
            "warning": ["", "Questionable", ""],
        }
    )


def plan(board, ids, slots):
    result = board.set_index("player_id").loc[ids].reset_index()
    result["slot"] = slots
    return result[["player_id", "slot", "projected_points"]]


def test_flex_move_cannot_hide_membership_change():
    board = roster()
    html, plain = render_lineup_brief(board, plan(board, ["c", "a"], ["RB1", "FLEX1"]))
    for output in [html, plain]:
        assert "Start: Charlie" in output
        assert "Bench: Bravo" in output
        assert "Alpha: RB1 to FLEX1" in output
        assert "+7.0 projected points" in output
        assert "Close call: Charlie / Bravo" in output
        assert "Limited history: 3 games" in output
        assert "Questionable" in output
        assert output.index("Your lineup actions") < output.index(
            "Recommended starters"
        )
        assert "01:00 PM EST" in output


def test_only_slot_shuffle_has_no_claimed_gain_or_replacement():
    board = roster()
    board.loc[1, "pos"] = "RB"
    html, plain = render_lineup_brief(board, plan(board, ["b", "a"], ["RB1", "FLEX1"]))
    for output in [html, plain]:
        assert "Keep your current offensive starters" in output
        assert "Slot assignments" in output
        assert "Lineup change:" not in output
        assert "Start:" not in output
        assert "Close call:" not in output


@pytest.mark.parametrize(
    "case", ["missing_points", "unavailable", "empty_slot", "duplicate_slot"]
)
def test_invalid_baseline_never_claims_a_gain(case):
    board = roster()
    if case == "missing_points":
        board.loc[1, "projected_points"] = float("nan")
    elif case == "unavailable":
        board.loc[1, "availability"] = "unavailable"
    elif case == "empty_slot":
        board.loc[1, "starter_slot"] = ""
    else:
        board.loc[1, "starter_slot"] = "RB1"
    _, text = render_lineup_brief(board, plan(board, ["a", "c"], ["RB1", "FLEX1"]))
    assert "Point gain unavailable" in text
    assert "Lineup change:" not in text
    assert "Close call:" not in text


def test_missing_or_disjoint_ranges_do_not_claim_overlap():
    board = roster()
    for lower in [float("nan"), 19.0]:
        board.loc[2, "prediction_lower"] = lower
        _, text = render_lineup_brief(board, plan(board, ["a", "c"], ["RB1", "FLEX1"]))
        assert "Close call:" not in text


def test_locked_values_and_html_escaping():
    board = roster()
    board.loc[0, "availability"] = "locked_starter"
    board.loc[0, "player_name"] = "<unsafe>"
    html, text = render_lineup_brief(board, plan(board, ["a", "b"], ["RB1", "FLEX1"]))
    assert "&lt;unsafe&gt;" in html and "<unsafe>" not in html
    assert "Locked starter; preweek estimate" in html
    assert "<unsafe>" in text


def test_kickoff_uses_daylight_or_standard_time_and_handles_missing():
    assert kickoff_label("2026-10-29T00:15:00Z") == "Wed Oct 28, 08:15 PM EDT"
    assert kickoff_label("2026-11-01T18:00:00Z") == "Sun Nov 01, 01:00 PM EST"
    assert kickoff_label(None) == "Kickoff unavailable"


def test_specialists_are_not_bench_actions_without_specialist_file():
    board = roster()
    specialist = board.iloc[[2]].copy()
    specialist["player_id"] = "def"
    specialist["player_name"] = "Defense"
    specialist["pos"] = "DEF"
    specialist["starter_slot"] = "DEF1"
    specialist["availability"] = "unsupported_position"
    full = pd.concat([board, specialist], ignore_index=True)
    _, text = render_lineup_brief(full, plan(board, ["a", "c"], ["RB1", "FLEX1"]))
    assert "Bench: Bravo\n" in text
    assert "+7.0 projected points" in text


def test_multiple_changes_show_membership_and_total_without_arbitrary_pairing():
    board = roster()
    extra = board.iloc[[2]].copy()
    extra["player_id"] = "d"
    extra["player_name"] = "Delta"
    full = pd.concat([board, extra], ignore_index=True)
    _, text = render_lineup_brief(full, plan(full, ["c", "d"], ["RB1", "FLEX1"]))
    assert "Start: Charlie, Delta" in text
    assert "Bench: Alpha, Bravo" in text
    assert "+10.0 projected points" in text
    assert "Close call:" not in text


def test_equivalent_numbered_slots_do_not_create_busywork():
    board = roster()
    board.loc[:1, "starter_slot"] = ["RB1", "RB2"]
    _, text = render_lineup_brief(board, plan(board, ["b", "a"], ["RB1", "RB2"]))
    assert "Keep your current offensive starters" in text
    assert "Slot assignments:" not in text


def test_bye_note_is_not_repeated():
    board = roster()
    board.loc[2, "availability"] = "no_scheduled_game"
    board.loc[2, "warning"] = "Bye or incomplete schedule; excluded"
    board.loc[2, "projected_points"] = float("nan")
    _, text = render_lineup_brief(board, plan(board, ["a", "b"], ["RB1", "FLEX1"]))
    assert text.count("Bye") == 1
    assert "Forecast unavailable" not in text
