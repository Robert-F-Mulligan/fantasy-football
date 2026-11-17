import pandas as pd

from fantasyfootball.trading.sellers import prioritize_pick_targets


def setup():
    roster = pd.DataFrame({"player_id": list("abcdef"), "roster_id": list(range(1, 7))})
    inventory = {
        "as_of": "2026-11-17",
        "standings_snapshot": [
            {
                "roster_id": i,
                "win_fraction": pct,
                "record": f"{int(pct * 10)}-{10 - int(pct * 10)}-0",
            }
            for i, pct in enumerate([0.9, 0.8, 0.7, 0.4, 0.2, 0.2], 1)
        ],
    }
    targets = [
        {"player_id": p, "marginal_ros_gain": gain}
        for p, gain in [("b", 100), ("c", 80), ("d", 60), ("e", 20), ("f", 30)]
    ]
    return targets, roster, inventory


def test_focus_changes_search_order_not_gains_and_includes_boundary_ties():
    targets, roster, inventory = setup()
    result, policy = prioritize_pick_targets(targets, roster, inventory, 1, limit=3)
    assert [r["player_id"] for r in result] == ["f", "e", "b"]
    assert result[0]["marginal_ros_gain"] == 30
    assert policy["priority_roster_ids"] == [5, 6]
    assert result[0]["seller"]["record"] == "2-8-0"


def test_all_tied_or_incomplete_standings_fall_back_to_value():
    targets, roster, inventory = setup()
    for r in inventory["standings_snapshot"]:
        r["win_fraction"] = 0.5
    result, policy = prioritize_pick_targets(targets, roster, inventory, 1)
    assert policy["status"] == "value_only" and result[0]["player_id"] == "b"
    inventory["standings_snapshot"].pop()
    result, policy = prioritize_pick_targets(targets, roster, inventory, 1)
    assert policy["status"] == "value_only"
    assert result[0]["seller"]["win_fraction"] is None


def test_invalid_fraction_is_not_treated_as_losing_record():
    targets, roster, inventory = setup()
    inventory["standings_snapshot"][0]["win_fraction"] = float("nan")
    result, policy = prioritize_pick_targets(targets, roster, inventory, 1)
    assert policy["status"] == "value_only"
    assert result[0]["player_id"] == "b"
