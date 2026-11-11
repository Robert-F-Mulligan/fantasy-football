from fantasyfootball.trading.pick_values import reprice_picks


def inventory():
    return {
        "draft_type": "snake",
        "picks": [
            {
                "round": rnd,
                "original_roster": 1,
                "owner_id": 2,
                "overall_earliest": (rnd - 1) * 2 + 1,
                "overall_latest": rnd * 2,
            }
            for rnd in [1, 2]
        ],
    }


def rosters(wins):
    return [
        {
            "roster_id": owner,
            "settings": {
                "wins": wins[i],
                "losses": 10 - wins[i],
                "ties": 0,
                "fpts": 1000,
            },
        }
        for i, owner in enumerate([1, 2])
    ]


def test_reprices_original_team_not_pick_owner_and_reverses_even_snake_rounds():
    before = reprice_picks(inventory(), rosters([8, 2]), order_rule="reverse_standings")
    after = reprice_picks(inventory(), rosters([2, 8]), order_rule="reverse_standings")
    assert (
        after["picks"][0]["value_scenario"]["capital_index"]
        > before["picks"][0]["value_scenario"]["capital_index"]
    )
    assert (
        after["picks"][1]["value_scenario"]["capital_index"]
        < before["picks"][1]["value_scenario"]["capital_index"]
    )
    assert "heuristic" in after["valuation_method"]


def test_random_order_does_not_change_prices_from_irrelevant_standings():
    before = reprice_picks(inventory(), rosters([8, 2]), order_rule="random")
    after = reprice_picks(inventory(), rosters([2, 8]), order_rule="random")
    assert (
        before["picks"][0]["value_scenario"]["capital_index"]
        == after["picks"][0]["value_scenario"]["capital_index"]
    )


def test_unknown_order_keeps_standings_price_conditional():
    report = reprice_picks(inventory(), rosters([2, 8]))
    value = report["picks"][0]["value_scenario"]
    assert value["estimated_overall"] == 1.5
    assert value["reverse_standings_if_season_ended_today"]["estimated_overall"] == 1
    assert value["index_low"] < value["capital_index"] < value["index_high"]


def test_missing_and_tied_standings_do_not_invent_a_slot():
    tied = reprice_picks(inventory(), rosters([5, 5]), order_rule="reverse_standings")
    assert tied["picks"][0]["value_scenario"]["estimated_overall"] == 1.5
    missing = reprice_picks(
        inventory(),
        [{"roster_id": 1}, {"roster_id": 2}],
        order_rule="reverse_standings",
    )
    assert (
        missing["picks"][0]["value_scenario"]["reverse_standings_if_season_ended_today"]
        is None
    )
