from copy import deepcopy

import pandas as pd

from fantasyfootball.trading.fairness import OfferFairness
from fantasyfootball.trading.service import TradeCalculator


def model():
    picks = [
        {
            "pick_id": f"2027:{r}:{o}",
            "round": r,
            "owner_id": o,
            "original_roster": o,
            "value_scenario": {
                "projected_overall_picks": [(r - 1) * 2 + o],
                "capital_index": 100 / ((r - 1) * 2 + o) ** 0.5,
            },
        }
        for r in range(1, 6)
        for o in [1, 2]
    ]
    return OfferFairness(
        {
            "annual_values": {"a": 100, "b": 80, "c": 60, "d": 40},
            "curve": [100, 80, 60, 40, 20, 10, 0, 0, 0, 0],
            "keeper_limit": 2,
            "rules": {"round_penalty": 2, "max_consecutive_keeps": 2},
            "draft_costs": {
                p: {"latest_round": 5, "original_round": 5, "consecutive_keeps": 0}
                for p in "abcd"
            },
            "inventory": {"rounds": 5, "status": "rounds_confirmed", "picks": picks},
            "assumptions": ["Sensitivity range, not CI"],
        }
    )


def test_keeper_cost_is_subtracted_and_one_pick_cannot_pay_twice():
    m = model()
    picks = [p for p in m.evidence["inventory"]["picks"] if p["owner_id"] == 1]
    base = m._future(set("abc"), picks, "none", 0)
    # All three cost R3; only one owned R3 pick, worth 20 points.
    assert m._future(set("abc"), picks, "latest", 0) - base == 80
    m.evidence["draft_costs"]["b"]["latest_round"] = 4
    # A at R3: +80; B at R2: +20. C cannot reuse R3.
    assert m._future(set("abc"), picks, "latest", 0) - base == 100


def test_keeper_limit_and_two_consecutive_keeps_expire_rights():
    m = model()
    picks = m.evidence["inventory"]["picks"]
    base = m._future(set("abcd"), picks, "none", 0)
    assert m._future(set("abcd"), picks, "latest", 0) - base == 150
    m.evidence["draft_costs"]["a"]["consecutive_keeps"] = 2
    assert m._future(set("abcd"), picks, "latest", 0) - base == 110


def calculator(m):
    roster = pd.DataFrame(
        {
            "player_id": list("abcd"),
            "roster_id": [1, 1, 2, 2],
            "pos": ["RB"] * 4,
            "tradable": [True] * 4,
        }
    )
    p = pd.DataFrame(
        {
            "player_id": list("abcd"),
            "week": [10] * 4,
            "status": ["projected"] * 4,
            "projected_points": [20, 10, 15, 5],
        }
    )
    return TradeCalculator(
        roster,
        p,
        {"RB": ["RB"]},
        [10],
        pick_inventory=m.evidence["inventory"],
        offer_fairness=m,
    )


def test_player_for_pick_gets_numeric_future_value_not_zero_or_market_units():
    m = model()
    result = calculator(m).evaluate(
        1, 2, [], ["c"], my_drops=["b"], give_picks=["2027:1:1"]
    )
    est = result["offer_estimate"]
    assert est["status"] == "conditional_estimate"
    assert est["scenario_count"] == 18
    no_keepers = [
        s
        for s in est["scenarios"]
        if s["keeper_mode"] == "none" and s["rank_shift"] == 0
    ]
    assert no_keepers[0]["my_future_change"] == -100
    assert no_keepers[0]["partner_future_change"] == 100
    assert est["acceptance_probability"] is None


def test_pick_swap_is_antisymmetric_without_keeper_rights():
    m = model()
    m.evidence["keeper_limit"] = 0
    c = calculator(m)
    r = c.evaluate(1, 2, [], [], give_picks=["2027:1:1"], receive_picks=["2027:3:2"])
    est = r["offer_estimate"]
    assert est["verdict"] == "favors_partner_in_modeled_scenarios"
    for s in est["scenarios"]:
        assert s["my_total_change"] == -s["partner_total_change"]


def test_noop_has_no_keeper_windfall_and_missing_forecasts_are_not_zero():
    m = model()
    c = calculator(m)
    result = {
        "status": "estimated",
        "give": [],
        "receive": [],
        "my_drops": [],
        "partner_drops": [],
        "give_picks": [],
        "receive_picks": [],
        "my_gain": 0,
        "partner_gain": 0,
    }
    assert m.assess(c, 1, 2, result)["my_total_change"] == {"low": 0, "high": 0}
    del m.evidence["annual_values"]["a"]
    assert m.assess(c, 1, 2, result)["status"] == "unavailable"


def test_draft_order_repricing_and_cost_of_trading_keeper_payment_pick():
    m = model()
    pick = deepcopy(m.evidence["inventory"]["picks"][0])
    assert m._pick_value(pick, 0) == 100
    pick["value_scenario"]["projected_overall_picks"] = [2]
    assert m._pick_value(pick, 0) == 80
    c = calculator(m)
    r = c.evaluate(1, 2, [], [], give_picks=["2027:3:1"], receive_picks=["2027:5:2"])
    latest = [
        s
        for s in r["offer_estimate"]["scenarios"]
        if s["keeper_mode"] == "latest" and s["rank_shift"] == 0
    ]
    # Lose R3's 20 draft points plus the 80-point keeper discount.
    assert latest[0]["my_future_change"] == -100


def test_annual_proxy_uses_per_game_not_remaining_week_count():
    players = pd.DataFrame({"player_id": ["a"], "pos": ["RB"]})
    replacements = pd.DataFrame({"player_id": ["w"], "pos": ["RB"]})
    participation = pd.DataFrame({"player_id": ["a", "w"], "probability": [1, 1]})

    def build(weeks):
        def frame(pid, points):
            return pd.DataFrame(
                {
                    "player_id": [pid] * len(weeks),
                    "week": weeks,
                    "status": ["projected"] * len(weeks),
                    "projected_points": [points] * len(weeks),
                }
            )

        return OfferFairness.build(
            players,
            frame("a", 20),
            replacements,
            frame("w", 10),
            participation,
            season=2026,
            weeks=weeks,
        )

    assert build([10, 11]).evidence["annual_values"]["a"] == 160
    assert build([16]).evidence["annual_values"]["a"] == 160


def test_historical_fallback_excludes_forecast_week_and_preserves_missing_history():
    players = pd.DataFrame({"player_id": ["a", "b"], "pos": ["RB", "RB"]})
    replacements = pd.DataFrame({"player_id": ["w"], "pos": ["RB"]})
    projections = pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "week": [10, 10],
            "status": ["unavailable", "unknown"],
            "projected_points": [None, None],
        }
    )
    alternatives = pd.DataFrame(
        {
            "player_id": ["w"],
            "week": [10],
            "status": ["projected"],
            "projected_points": [10],
        }
    )
    participation = pd.DataFrame(
        {"player_id": ["a", "b", "w"], "probability": [1, 1, 1]}
    )
    history = pd.DataFrame(
        {
            "player_id": ["a"] * 5,
            "season": [2026] * 5,
            "week": [6, 7, 8, 9, 10],
            "fantasy_points": [20, 20, 20, 20, 9999],
        }
    )
    m = OfferFairness.build(
        players,
        projections,
        replacements,
        alternatives,
        participation,
        season=2026,
        weeks=[10],
        history=history,
    )
    assert m.evidence["annual_values"]["a"] == 160
    assert "b" not in m.evidence["annual_values"]
    assert m.evidence["historical_fallback_player_ids"] == ["a"]


def test_rendered_email_includes_conditional_estimate_and_no_acceptance_odds():
    from fantasyfootball.reports.trades import render_trades

    c = calculator(model())
    result = c.evaluate(1, 2, ["b"], ["c"])
    report = {
        "season": 2026,
        "week": 10,
        "as_of": "2026-11-11",
        "status": "estimated",
        "weeks": [10],
        "opportunities": [result],
        "players": {p: {"name": p, "pos": "RB", "team": "TEST"} for p in "abcd"},
    }
    _, plain, html = render_trades(report, "Team")
    assert "Two-season value change" in plain and "Two-season value change" in html
    assert "Sensitivity range, not a confidence interval" in plain


def test_fairness_evidence_json_round_trip_preserves_estimate():
    import json

    m = model()
    original = calculator(m).evaluate(1, 2, ["b"], ["c"])["offer_estimate"]
    loaded = OfferFairness(json.loads(json.dumps(m.evidence)))
    assert calculator(loaded).evaluate(1, 2, ["b"], ["c"])["offer_estimate"] == original
