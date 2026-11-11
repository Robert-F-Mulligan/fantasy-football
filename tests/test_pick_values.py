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


def test_twelve_team_snake_projection_reverses_even_round_and_follows_original_owner():
    data = [
        {
            "roster_id": i,
            "settings": {"wins": i - 1, "losses": 12 - i, "ties": 0, "fpts": i * 100},
        }
        for i in range(1, 13)
    ]
    assets = {
        "draft_type": "snake",
        "picks": [
            {
                "round": r,
                "original_roster": 7,
                "owner_id": 1,
                "overall_earliest": (r - 1) * 12 + 1,
                "overall_latest": r * 12,
            }
            for r in [1, 2, 3]
        ],
    }
    result = reprice_picks(assets, data, order_rule="reverse_standings")
    assert [p["value_scenario"]["selection"] for p in result["picks"]] == [
        "1.07",
        "2.06",
        "3.07",
    ]
    assert [
        p["value_scenario"]["projected_overall_picks"] for p in result["picks"]
    ] == [[7], [18], [31]]


def test_exact_ties_show_selection_range_not_a_fictional_fractional_pick():
    result = reprice_picks(inventory(), rosters([5, 5]), order_rule="reverse_standings")
    assert result["picks"][0]["value_scenario"]["selection"] == "1.01-1.02"
    assert result["picks"][1]["value_scenario"]["projected_overall_picks"] == [3, 4]


def test_pick_email_shows_projected_selection_and_overall_number():
    from fantasyfootball.reports.trades import render_trades

    picks = reprice_picks(inventory(), rosters([2, 8]), order_rule="reverse_standings")
    picks.update(status="rounds_confirmed", rounds=15, season=2027)
    report = {
        "season": 2026,
        "week": 10,
        "as_of": "2026-11-11T12:00:00Z",
        "status": "estimated",
        "weeks": [10, 17],
        "opportunities": [],
        "my_roster": 2,
        "pick_inventory": picks,
    }
    _, text, html = render_trades(report, "Team")
    assert "projected 1.01, overall 1" in text
    assert "projected 2.02, overall 4" in text
    assert "if the season ended today" in html
