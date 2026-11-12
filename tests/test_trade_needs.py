import pandas as pd
import pytest

from fantasyfootball.trading.service import TradeCalculator
from fantasyfootball.trading.value import RestOfSeasonValue, participation_estimates


def build(rows, scores, *, slots=None, probability=None, waivers=(), byes=()):
    slots = slots or {"RB1": ["RB"], "WR1": ["WR"]}
    roster = pd.DataFrame(
        [
            {"player_id": pid, "roster_id": owner, "pos": pos, "tradable": True}
            for pid, owner, pos in rows
        ]
    )
    pool = pd.DataFrame(waivers, columns=["player_id", "pos"])

    def forecast(ids):
        return pd.DataFrame(
            [
                {
                    "player_id": pid,
                    "week": week,
                    "status": "bye" if (pid, week) in byes else "projected",
                    "projected_points": scores[pid],
                }
                for week in [10, 11]
                for pid in ids
            ],
            columns=["player_id", "week", "status", "projected_points"],
        )

    projections, alternatives = forecast(roster.player_id), forecast(pool.player_id)
    players = list(roster.player_id) + list(pool.player_id)
    rates = pd.DataFrame(
        {
            "player_id": players,
            "probability": [(probability or {}).get(p, 1) for p in players],
        }
    )
    model = RestOfSeasonValue(
        roster, projections, pool, alternatives, rates, slots, [10, 11], samples=256
    )
    return TradeCalculator(
        roster, projections, slots, [10, 11], value_model=model
    ), model


@pytest.mark.parametrize("own_rb,own_wr,expected", [(20, 5, "WR"), (5, 20, "RB")])
def test_relative_strength_and_targets_change_with_roster_not_a_fixed_priority(
    own_rb, own_wr, expected
):
    c, model = build(
        [("r", 1, "RB"), ("w", 1, "WR"), ("r2", 2, "RB"), ("w2", 2, "WR")],
        {"r": own_rb, "w": own_wr, "r2": 15, "w2": 15},
    )
    targets = model.targets(c.roster, 1)
    assert c.players.loc[targets[0]["player_id"], "pos"] == expected
    strengths = {r["position"]: r for r in model.strengths(c.roster, 1)}
    assert strengths[expected]["rank"] == 2


def test_bye_qb_is_priced_above_real_waiver_alternative_not_zero():
    rows = [
        ("q", 1, "QB"),
        ("r", 1, "RB"),
        ("rb", 1, "RB"),
        ("q2", 2, "QB"),
        ("q2b", 2, "QB"),
        ("r2", 2, "RB"),
    ]
    scores = {
        "q": 25,
        "r": 20,
        "rb": 15,
        "q2": 24,
        "q2b": 23,
        "r2": 5,
        "wq": 20,
        "wr": 2,
    }
    c, _ = build(
        rows,
        scores,
        slots={"QB1": ["QB"], "RB1": ["RB"]},
        waivers=[("wq", "QB"), ("wr", "RB")],
        byes=[("q", 11)],
    )
    assert c.evaluate(1, 2, ["rb"], ["q2"])["my_gain"] == 4
    risky, _ = build(
        rows,
        scores,
        slots={"QB1": ["QB"], "RB1": ["RB"]},
        waivers=[("wq", "QB"), ("wr", "RB")],
        byes=[("q", 11)],
        probability={"r": 0.5},
    )
    assert risky.evaluate(1, 2, ["rb"], ["q2"])["my_gain"] < 0


def test_bench_depth_has_value_when_starter_may_be_absent():
    _c, model = build(
        [("r", 1, "RB"), ("b", 1, "RB"), ("x", 2, "RB")],
        {"r": 20, "b": 10, "x": 15, "w": 2},
        slots={"RB1": ["RB"]},
        waivers=[("w", "RB")],
        probability={"r": 0.5},
    )
    assert model.total({"r", "b"}) - model.total({"r"}) > 6
    assert model.total({"r", "b"}) == model.total({"b", "r"})


def test_other_positions_can_be_best_and_package_accounting_reconciles():
    c, _ = build(
        [
            ("r", 1, "RB"),
            ("rb", 1, "RB"),
            ("t", 1, "TE"),
            ("t2", 2, "TE"),
            ("t2b", 2, "TE"),
            ("r2", 2, "RB"),
        ],
        {"r": 20, "rb": 18, "t": 5, "t2": 20, "t2b": 18, "r2": 5},
        slots={"RB1": ["RB"], "TE1": ["TE"]},
    )
    trades = c.opportunities(1)
    assert trades and c.players.loc[trades[0]["receive"][0], "pos"] == "TE"
    trade = trades[0]
    assessment = trade["recommendation"]
    assert assessment["incoming_marginal_value"] - assessment[
        "outgoing_opportunity_cost"
    ] == pytest.approx(trade["my_gain"])


def test_known_owned_player_cannot_be_used_as_a_free_replacement():
    with pytest.raises(ValueError, match="owned"):
        build([("r", 1, "RB")], {"r": 10}, slots={"RB1": ["RB"]}, waivers=[("r", "RB")])


def test_participation_proxy_uses_only_past_scheduled_team_opportunities():
    players = pd.DataFrame(
        {"player_id": ["a", "b"], "team": ["NE", "NE"], "pos": ["RB", "RB"]}
    )
    history = pd.DataFrame(
        {
            "player_id": ["a"] * 3,
            "team": ["NE"] * 3,
            "season": [2026] * 3,
            "week": [7, 9, 11],
        }
    )
    schedule = pd.DataFrame(
        {
            "season": [2026] * 5,
            "week": [7, 8, 9, 10, 11],
            "game_type": ["REG"] * 5,
            "home_team": ["NE"] * 5,
            "away_team": ["BUF"] * 5,
        }
    )
    rates = participation_estimates(players, history, schedule, 2026, 10).set_index(
        "player_id"
    )
    assert rates.loc["a", "probability"] == pytest.approx(3 / 5)
    assert rates.loc["a", "opportunities"] == 3
    assert "fallback" in rates.loc["b", "source"]


def test_email_explains_roster_relative_value_without_an_rb_rule():
    from fantasyfootball.reports.trades import render_trades

    r = {
        "week": 10,
        "season": 2026,
        "as_of": "2026-11-10T15:00:00Z",
        "status": "estimated",
        "weeks": [10, 11, 12, 13, 14, 15, 16, 17],
        "opportunities": [],
        "roster_strengths": [
            {
                "position": "TE",
                "ros_value_above_replacement": 10,
                "league_median": 20,
                "rank": 9,
                "teams_evaluated": 12,
            }
        ],
    }
    _, text, html = render_trades(r, "Team")
    assert "rank 9 among 12 modeled teams" in text and "Trade priority" not in text
    assert "No evaluated one-for-one package" in text
    assert "Your roster relative to the league" in html
