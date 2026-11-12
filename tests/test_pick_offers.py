import pandas as pd

from fantasyfootball.reports.trades import render_trades
from fantasyfootball.trading.fairness import OfferFairness
from fantasyfootball.trading.pick_offers import pick_trade_scenarios
from fantasyfootball.trading.service import TradeCalculator


def calculator():
    picks = [
        {
            "pick_id": f"2027:{r}:{o}",
            "season": 2027,
            "round": r,
            "owner_id": o,
            "original_roster": o,
            "value_scenario": {
                "projected_overall_picks": [(r - 1) * 2 + o],
                "capital_index": 100 / ((r - 1) * 2 + o) ** 0.5,
                "selection": f"{r}.{o:02d}",
            },
        }
        for r in range(1, 4)
        for o in [1, 2]
    ]
    inventory = {
        "season": 2027,
        "status": "rounds_confirmed",
        "rounds": 3,
        "picks": picks,
    }
    fairness = OfferFairness(
        {
            "annual_values": dict.fromkeys("abcd", 100),
            "curve": [100, 80, 60, 40, 20, 10],
            "keeper_limit": 0,
            "rules": {},
            "draft_costs": {},
            "inventory": inventory,
            "assumptions": [],
        }
    )
    roster = pd.DataFrame(
        {
            "player_id": list("abcd"),
            "roster_id": [1, 1, 2, 2],
            "pos": ["RB"] * 4,
            "tradable": [True] * 4,
        }
    )
    projections = pd.DataFrame(
        {
            "player_id": list("abcd"),
            "week": [10] * 4,
            "status": ["projected"] * 4,
            "projected_points": [20, 10, 60, 5],
        }
    )
    return TradeCalculator(
        roster,
        projections,
        {"RB": ["RB"]},
        [10],
        pick_inventory=inventory,
        offer_fairness=fairness,
    )


def test_real_owned_pick_prices_and_explicit_drop_are_compared():
    c = calculator()
    result = pick_trade_scenarios(c, 1, ["c"])
    assert len(result["offers"]) == 3
    assert [o["pick"]["round"] for o in result["offers"]] == [1, 2, 3]
    for o in result["offers"]:
        trade = o["trade"]
        assert not trade["give"] and trade["receive"] == ["c"]
        assert len(trade["my_drops"]) == 1 and trade["my_drops"][0] in {"a", "b"}
        assert trade["give_picks"][0]["owner_id"] == 1
        assert trade["my_gain"] == 40 and trade["partner_gain"] == -55
    assert result["offers"][0]["decision"] == "too_expensive"
    assert result["offers"][2]["decision"] == "seller_loses"
    assert (
        result["offers"][0]["reference"]["my_total_change"]
        < result["offers"][2]["reference"]["my_total_change"]
    )


def test_transferred_pick_ownership_and_unavailable_future_evidence():
    c = calculator()
    for p in c.pick_inventory["picks"]:
        if p["round"] == 1:
            p["owner_id"] = 3 - p["owner_id"]
    result = pick_trade_scenarios(c, 1, ["c", "c", "a", "missing"])
    assert len(result["offers"]) == 3
    assert result["offers"][0]["pick"]["original_roster"] == 2
    c.offer_fairness = None
    assert all(
        o["decision"] == "unpriced" for o in pick_trade_scenarios(c, 1, ["c"])["offers"]
    )
    c.pick_inventory["trades_disabled"] = True
    assert pick_trade_scenarios(c, 1, ["c"])["status"] == "unavailable"


def test_unknown_current_forecasts_do_not_make_zero_cost_offers():
    c = calculator()
    c.projections.loc[("d", 10), "status"] = "unknown"
    result = pick_trade_scenarios(c, 1, ["c"])
    assert len(result["offers"]) == 3
    assert all(o["status"] == "unavailable" for o in result["offers"])


def test_email_distinguishes_twelve_team_league_from_eleven_modeled_teams():
    c = calculator()
    report = {
        "season": 2026,
        "week": 10,
        "weeks": [10],
        "as_of": "2026-11-12",
        "status": "estimated",
        "league_team_count": 12,
        "opportunities": [],
        "players": {p: {"name": p, "pos": "RB", "team": "AAA"} for p in "abcd"},
        "roster_strengths": [
            {
                "position": "RB",
                "ros_value_above_replacement": 20,
                "league_median": 30,
                "rank": 9,
                "teams_evaluated": 11,
            }
        ],
        "pick_trade_scenarios": pick_trade_scenarios(c, 1, ["c"]),
    }
    _, plain, html = render_trades(report, "Team")
    assert "12-team league" in plain and "11 of 12" in html
    assert "among 11 modeled teams" in plain
    assert "2027 1.01" in plain and "2027 3.01" in plain
    assert "drop " in plain and "seller range" in plain
    assert "Players for next-year picks" in html
