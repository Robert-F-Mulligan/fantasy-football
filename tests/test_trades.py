import json
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from fantasyfootball.reports.trades import render_trades
from fantasyfootball.trading.application import build_trade_report
from fantasyfootball.trading.service import TradeCalculator


def fixture():
    roster = pd.DataFrame(
        [
            {"player_id": p, "roster_id": owner, "pos": pos, "tradable": True}
            for p, owner, pos in [
                ("a", 1, "RB"),
                ("b", 1, "RB"),
                ("c", 1, "WR"),
                ("d", 2, "WR"),
                ("e", 2, "WR"),
                ("f", 2, "RB"),
            ]
        ]
    )
    projections = pd.DataFrame(
        [
            {
                "player_id": p,
                "week": w,
                "projected_points": value,
                "status": "projected",
            }
            for w in [8, 9]
            for p, value in zip("abcdef", [20, 18, 5, 20, 18, 5])
        ]
    )
    return roster, projections


def calculator(slots=None):
    roster, projections = fixture()
    return TradeCalculator(
        roster, projections, slots or {"RB1": ["RB"], "WR1": ["WR"]}, [8, 9]
    )


def test_surplus_trade_improves_both_actual_lineups():
    c = calculator()
    result = c.evaluate(1, 2, ["b"], ["e"])
    assert result["my_gain"] == result["partner_gain"] == 26
    assert result["weekly"][0]["my_before"]["points"] == 25
    assert result["weekly"][0]["my_after"]["points"] == 38
    assert len(c.opportunities(1)) == 1


def test_flex_changes_trade_value_without_double_counting():
    c = calculator({"RB1": ["RB"], "WR1": ["WR"], "FLEX1": ["RB", "WR", "TE"]})
    result = c.evaluate(1, 2, ["b"], ["e"])
    assert result["my_gain"] == result["partner_gain"] == 0
    assert c.opportunities(1) == []


def test_byes_are_zero_coverage_but_unknowns_are_not_zero_points():
    roster, p = fixture()
    p.loc[p.player_id.eq("e") & p.week.eq(9), "status"] = "bye"
    result = TradeCalculator(
        roster, p, {"RB1": ["RB"], "WR1": ["WR"]}, [8, 9]
    ).evaluate(1, 2, ["b"], ["e"])
    assert result["my_gain"] == 13
    p.loc[p.player_id.eq("e") & p.week.eq(9), "status"] = "unknown"
    result = TradeCalculator(
        roster, p, {"RB1": ["RB"], "WR1": ["WR"]}, [8, 9]
    ).evaluate(1, 2, ["b"], ["e"])
    assert result["status"] == "incomplete" and result["my_gain"] is None


def test_unequal_trade_requires_drop_and_validates_ownership():
    c = calculator()
    with pytest.raises(ValueError, match="increase active roster"):
        c.evaluate(1, 2, ["a", "b"], ["e"])
    result = c.evaluate(1, 2, ["a", "b"], ["e"], partner_drops=["f"])
    assert result["weekly"][0]["my_after"]["filled"] == 1
    with pytest.raises(ValueError, match="belong"):
        c.evaluate(1, 2, ["d"], ["b"])
    with pytest.raises(ValueError, match="overlap"):
        c.evaluate(1, 2, ["b"], ["e"], my_drops=["b"])


def test_negative_projection_fills_required_slot():
    roster, p = fixture()
    p.loc[p.player_id.eq("f"), "projected_points"] = -2
    c = TradeCalculator(roster, p, {"RB1": ["RB"], "WR1": ["WR"]}, [8])
    assert c.evaluate(1, 2, ["b"], ["e"])["weekly"][0]["partner_before"]["points"] == 18


def test_injured_players_not_proposed_or_accepted():
    c = calculator()
    c.roster.loc[c.roster.player_id.isin(["a", "b", "c"]), "tradable"] = False
    c.players.loc["b", "tradable"] = False
    assert c.opportunities(1) == []
    with pytest.raises(ValueError, match="Injured"):
        c.evaluate(1, 2, ["b"], ["e"])


def test_render_trade_units_escape_and_no_fabricated_confidence():
    report = {
        "week": 8,
        "season": 2026,
        "as_of": "2026-10-27T14:00:00Z",
        "status": "estimated",
        "weeks": [8, 9],
        "players": {
            p: {"name": "<script>" + p, "team": "NE", "pos": "RB"} for p in "abcdef"
        },
        "opportunities": [calculator().evaluate(1, 2, ["b"], ["e"])],
    }
    subject, text, html = render_trades(report, "Team")
    assert "Trade Opportunities" in subject
    assert "+26.0 points total" in text
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "do not have calibrated confidence intervals" in text
    assert 'scope="col"' in html and 'charset="utf-8"' in html


def test_closed_deadline_does_not_train_or_offer_trades(tmp_path):
    (tmp_path / "import-report.json").write_text(
        json.dumps(
            {"season": 2026, "roster_id": 1, "waiver_settings": {"trade_deadline": 8}}
        )
    )
    pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 8,
                "game_type": "REG",
                "gameday": "2026-10-29",
                "gametime": "20:15",
            }
        ]
    ).to_csv(tmp_path / "schedule.csv", index=False)
    args = SimpleNamespace(
        league_dir=tmp_path,
        schedule=tmp_path / "schedule.csv",
        season=2026,
        week=8,
        as_of="2026-10-30T14:00:00Z",
        output=tmp_path,
    )
    report = build_trade_report(args)
    assert report["status"] == "closed" and report["opportunities"] == []
    assert "closed" in render_trades(report, "Team")[1]


@pytest.mark.parametrize("started,expected_start", [(False, 8), (True, 9)])
def test_builder_uses_one_pregame_fit_and_separate_future_weeks(
    tmp_path, monkeypatch, started, expected_start
):
    import fantasyfootball.trading.application as app

    roster, _ = fixture()
    roster["sleeper_id"] = roster.player_id
    roster["player_name"] = roster.player_id
    roster["is_reserve"] = False
    roster["is_taxi"] = False
    roster.to_csv(tmp_path / "rosters.csv", index=False)
    (tmp_path / "import-report.json").write_text(
        json.dumps(
            {"season": 2026, "roster_id": 1, "waiver_settings": {"trade_deadline": 0}}
        )
    )
    (tmp_path / "offensive-slots.json").write_text(
        json.dumps({"RB1": ["RB"], "WR1": ["WR"]})
    )
    (tmp_path / "league-supported-offense.json").write_text("{}")
    (tmp_path / "players.json").write_text(
        json.dumps({p: {"position": "RB", "status": "Active"} for p in "abcdef"})
    )
    pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 8,
                "game_type": "REG",
                "gameday": "2026-10-29",
                "gametime": "20:15",
            }
        ]
    ).to_csv(tmp_path / "schedule.csv", index=False)
    pd.DataFrame({"season": [2026, 2026], "week": [7, 8]}).to_csv(
        tmp_path / "history.csv", index=False
    )
    monkeypatch.setattr(
        app, "league_from_dict", lambda _: SimpleNamespace(scoring=None)
    )

    def prepare(frame, scoring):
        assert frame.week.tolist() == [
            7
        ]  # Current week cannot enter training, even after kickoff.
        return frame.assign(player_id="a", fantasy_points=20.0)

    monkeypatch.setattr(app, "prepare_weekly", prepare)
    model = Mock(cutoff=202607)
    model.fit.return_value = model

    def predict(*, fixtures):
        assert fixtures.week.nunique() == 1
        result = fixtures.copy()
        result["projected_points"] = result.player_id.map(
            dict(zip("abcdef", [20, 18, 5, 20, 18, 5]))
        )
        result["history_games"] = 10
        return result

    model.predict.side_effect = predict
    monkeypatch.setattr(app, "FactorModel", lambda _: model)
    planner = Mock()

    def available(roster, details, schedule, **kw):
        frame = roster.copy()
        frame["week"] = kw["week"]
        frame["season"] = 2026
        frame["opp"] = "BUF"
        frame["team"] = "NE"
        frame["injury_status"] = ""
        frame["availability"] = "eligible"
        return frame

    planner.availability.side_effect = available
    monkeypatch.setattr(app, "WeeklyLineupPlanner", lambda: planner)
    monkeypatch.setattr(
        "fantasyfootball.trading.replacements.replacement_pool",
        lambda *args: roster.iloc[:0].copy(),
    )
    monkeypatch.setattr(
        "fantasyfootball.trading.value.participation_estimates",
        lambda players, *args: pd.DataFrame(
            {"player_id": players.player_id, "probability": 1.0}
        ),
    )

    args = SimpleNamespace(
        league_dir=tmp_path,
        schedule=tmp_path / "schedule.csv",
        players=tmp_path / "players.json",
        input=tmp_path / "history.csv",
        output=tmp_path,
        season=2026,
        week=8,
        as_of="2026-10-30T14:00:00Z" if started else "2026-10-27T14:00:00Z",
    )
    report = build_trade_report(args)
    assert report["weeks"] == list(range(expected_start, 18))
    model.fit.assert_called_once()
    assert model.predict.call_count == 18 - expected_start
    assert report["opportunities"][0]["my_gain"] == 15 * (18 - expected_start)
    loaded, _saved = app.load_calculator(tmp_path)
    assert loaded.evaluate(1, 2, ["b"], ["e"])["my_gain"] == 13 * (18 - expected_start)
