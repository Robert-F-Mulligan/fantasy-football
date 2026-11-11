import pandas as pd

from fantasyfootball.trading.service import TradeCalculator


def make(rows, values, priorities=("RB",), slots=None, byes=()):
    roster = pd.DataFrame(
        [
            {"player_id": pid, "roster_id": owner, "pos": pos, "tradable": True}
            for pid, owner, pos in rows
        ]
    )
    projections = pd.DataFrame(
        [
            {
                "player_id": pid,
                "week": week,
                "projected_points": value,
                "status": "bye" if (pid, week) in byes else "projected",
            }
            for week in [10, 11]
            for pid, value in values.items()
        ]
    )
    return TradeCalculator(
        roster,
        projections,
        slots or {"RB1": ["RB"], "WR1": ["WR"]},
        [10, 11],
        priority_positions=priorities,
    )


def test_rb_surplus_by_count_does_not_make_rbs_expendable_when_rb_is_priority():
    c = make(
        [
            ("r1", 1, "RB"),
            ("r2", 1, "RB"),
            ("r3", 1, "RB"),
            ("w", 1, "WR"),
            ("x", 2, "WR"),
            ("y", 2, "WR"),
            ("z", 2, "RB"),
        ],
        {"r1": 12, "r2": 11, "r3": 10, "w": 4, "x": 20, "y": 18, "z": 2},
    )
    result = c.evaluate(1, 2, ["r3"], ["y"])
    assert result["my_gain"] > 0 and result["partner_gain"] > 0
    assert not result["recommendation"]["eligible"]
    assert "Reduces RB roster depth" in result["recommendation"]["reasons"]
    assert c.opportunities(1) == []


def test_real_rb_upgrade_from_surplus_wr_is_recommended():
    c = make(
        [
            ("r", 1, "RB"),
            ("rb", 1, "RB"),
            ("w", 1, "WR"),
            ("wb", 1, "WR"),
            ("x", 2, "RB"),
            ("xb", 2, "RB"),
            ("y", 2, "WR"),
        ],
        {"r": 5, "rb": 3, "w": 20, "wb": 18, "x": 20, "xb": 18, "y": 5},
    )
    recommendations = c.opportunities(1)
    assert recommendations
    best = recommendations[0]
    assert c.players.loc[best["receive"][0], "pos"] == "RB"
    assert c.players.loc[best["give"][0], "pos"] == "WR"
    assert best["recommendation"]["priority_gain"] > 0
    assert all(
        row["after"]["available"] >= row["before"]["available"]
        for row in best["recommendation"]["position_impact"]
    )


def test_bye_week_qb_patch_is_not_a_trade_recommendation_even_without_priority():
    c = make(
        [
            ("q", 1, "QB"),
            ("r", 1, "RB"),
            ("rb", 1, "RB"),
            ("x", 2, "QB"),
            ("xb", 2, "QB"),
            ("y", 2, "RB"),
        ],
        {"q": 25, "r": 20, "rb": 15, "x": 20, "xb": 19, "y": 5},
        priorities=(),
        slots={"QB1": ["QB"], "RB1": ["RB"]},
        byes=[("q", 11)],
    )
    result = c.evaluate(1, 2, ["rb"], ["x"])
    assert result["my_gain"] == 20 and result["partner_gain"] > 0
    assert not result["recommendation"]["eligible"]
    assert any("bye-week patch" in text for text in result["recommendation"]["reasons"])
    assert c.opportunities(1) == []


def test_rb_trade_cannot_create_a_new_bye_week_depth_hole():
    c = make(
        [
            ("r", 1, "RB"),
            ("rb", 1, "RB"),
            ("w", 1, "WR"),
            ("x", 2, "RB"),
            ("xb", 2, "RB"),
            ("y", 2, "WR"),
        ],
        {"r": 10, "rb": 8, "w": 20, "x": 25, "xb": 20, "y": 5},
        byes=[("x", 11)],
    )
    result = c.evaluate(1, 2, ["r"], ["x"])
    assert not result["recommendation"]["eligible"]
    assert any("week 11" in text for text in result["recommendation"]["reasons"])


def test_multi_player_custom_trade_exposes_rb_depth_warning():
    c = make(
        [
            ("r", 1, "RB"),
            ("rb", 1, "RB"),
            ("w", 1, "WR"),
            ("x", 2, "RB"),
            ("xb", 2, "RB"),
            ("y", 2, "WR"),
        ],
        {"r": 10, "rb": 8, "w": 20, "x": 25, "xb": 20, "y": 5},
    )
    result = c.evaluate(1, 2, ["r", "rb"], ["x"], partner_drops=["xb"])
    assert "Reduces RB roster depth" in result["recommendation"]["reasons"]


def test_email_explains_priority_and_empty_result_without_fallback_qb_offers():
    from fantasyfootball.reports.trades import render_trades

    report = {
        "week": 10,
        "season": 2026,
        "as_of": "2026-11-10T15:00:00Z",
        "status": "estimated",
        "weeks": [10, 11],
        "priority_positions": ["RB"],
        "opportunities": [],
    }
    _, text, html = render_trades(report, "Team")
    assert "Trade priority: improve RB starters" in text
    assert "No evaluated one-for-one trade met the roster-needs" in text
    assert "Bye-week patches are excluded" in html
