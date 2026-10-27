import json

import pandas as pd
import pytest

from fantasyfootball.reports.waivers import render_waivers
from fantasyfootball.waivers.comparisons import AddDropEvaluator


def fixture():
    roster = pd.DataFrame(
        [
            {
                "player_id": "a",
                "player_name": "Starter",
                "pos": "RB",
                "starter_slot": "RB1",
            },
            {
                "player_id": "b",
                "player_name": "Bench WR",
                "pos": "WR",
                "starter_slot": "",
            },
            {
                "player_id": "c",
                "player_name": "Bench TE",
                "pos": "TE",
                "starter_slot": "",
            },
        ]
    ).assign(availability="eligible", locked_slot="", is_reserve=False, is_taxi=False)
    points = roster[["player_id"]].assign(projected_points=[10.0, 8.0, 12.0])
    candidate = pd.DataFrame(
        [
            {
                "player_id": "x",
                "player_name": "Pickup",
                "pos": "WR",
                "projected_points": 9.0,
            }
        ]
    )
    available = candidate.drop(columns="projected_points").assign(
        availability="eligible",
        locked_slot="",
        starter_slot="",
        is_reserve=False,
        is_taxi=False,
    )
    return (
        roster,
        points,
        available,
        candidate,
        {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]},
    )


def test_net_gain_includes_production_lost_by_drop_and_flex():
    result = AddDropEvaluator().evaluate(*fixture()).set_index("drop_player_id")
    assert set(result.index) == {"b", "c"}
    assert result.loc["b", "net_gain"] == 0
    assert result.loc["c", "net_gain"] == -3  # Full roster gain alone would be zero.
    assert result.loc["c", "after_points"] == 19


@pytest.mark.parametrize("protection", ["reserve", "taxi", "locked_bench", "assigned"])
def test_protected_players_never_appear_as_drops(protection):
    roster, points, available, candidate, slots = fixture()
    if protection in {"reserve", "taxi"}:
        roster.loc[roster.player_id.eq("c"), "is_" + protection] = True
    elif protection == "assigned":
        roster.loc[roster.player_id.eq("c"), "starter_slot"] = "FLEX1"
    else:
        roster.loc[roster.player_id.eq("c"), "availability"] = protection
    result = AddDropEvaluator().evaluate(roster, points, available, candidate, slots)
    assert "c" not in set(result.drop_player_id)


def test_locked_flex_stays_fixed_even_for_better_pickup():
    roster, points, available, candidate, slots = fixture()
    roster.loc[
        roster.player_id.eq("b"), ["availability", "locked_slot", "starter_slot"]
    ] = ["locked_starter", "FLEX1", "FLEX1"]
    candidate["projected_points"] = 30
    result = AddDropEvaluator().evaluate(roster, points, available, candidate, slots)
    assert result.drop_player_id.tolist() == ["c"]
    assert result.net_gain.tolist() == [0]


def test_unfillable_pair_is_not_returned():
    roster, points, available, candidate, _ = fixture()
    result = AddDropEvaluator().evaluate(
        roster, points, available, candidate, {"RB1": ["RB"], "TE1": ["TE"]}
    )
    assert result.drop_player_id.tolist() == ["b"]


def test_owned_duplicate_or_locked_candidates_not_compared():
    args = list(fixture())
    args[2]["availability"] = "locked_bench"
    assert AddDropEvaluator().evaluate(*args).empty
    args = list(fixture())
    args[3] = pd.concat([args[3], args[3]], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        AddDropEvaluator().evaluate(*args)
    args = list(fixture())
    args[3]["player_id"] = "a"
    with pytest.raises(ValueError, match="already"):
        AddDropEvaluator().evaluate(*args)


def test_email_shows_signed_changes_and_escapes_names(tmp_path):
    pd.DataFrame(columns=["category"]).to_csv(tmp_path / "waivers.csv", index=False)
    (tmp_path / "waiver-report.json").write_text(
        json.dumps(
            {
                "categories": [],
                "limits": "Scope",
                "lineup_gain_note": "Conditional",
                "add_drop_note": "One-week what-if",
            }
        ),
        encoding="utf-8",
    )
    result = AddDropEvaluator().evaluate(*fixture())
    result["add_player_name"] = "<unsafe>"
    result.to_csv(tmp_path / "waiver-add-drop.csv", index=False)
    html, plain = render_waivers(tmp_path)
    assert "&lt;unsafe&gt;" in html and "<unsafe>" not in html
    assert "-3.0" in html and "+0.0" in plain and "One-week what-if" in plain


def test_saved_csv_empty_locks_do_not_become_fixed_slots():
    args = list(fixture())
    args[0]["locked_slot"] = float("nan")
    args[2]["locked_slot"] = float("nan")
    assert len(AddDropEvaluator().evaluate(*args)) == 2
