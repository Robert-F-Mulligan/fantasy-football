import json

import numpy as np
import pandas as pd
import pytest

from fantasyfootball.trading.uncertainty import (
    TradePredictionRanges,
    exposure,
    planned_lineup,
    replay_trades,
)


def records():
    return pd.DataFrame(
        [
            {
                "season": season,
                "origin": season * 100 + origin,
                "horizon": 8,
                "expected": 10 + i,
                "actual": 10 + i + (i % 5 - 2) * 5,
                "exposure": 16,
            }
            for season in [2024, 2025]
            for origin in [5, 7, 9]
            for i in range(20)
        ]
    )


def test_validation_outcomes_cannot_choose_width_or_residual_distribution():
    data = records()
    a = TradePredictionRanges.fit(data, 8)
    data.loc[data.season.eq(2025), "actual"] = 10000
    b = TradePredictionRanges.fit(data, 8)
    assert a.evidence["errors"] == b.evidence["errors"]
    assert a.evidence["scaled_half_width"] == b.evidence["scaled_half_width"]
    assert b.evidence["observed_coverage"] == 0
    assert a.evidence["calibration_seasons"] == [2024]
    assert a.evidence["validation_season"] == 2025


def test_wrong_horizon_and_small_origin_count_do_not_invent_interval():
    m = TradePredictionRanges.fit(records(), 8)
    assert m.apply(10, 4, 8)["status"] == "unavailable"
    one = records().loc[lambda d: d.origin.mod(100).eq(5)]
    assert (
        TradePredictionRanges.fit(one, 8).evidence["status"] == "insufficient_evidence"
    )
    assert (
        TradePredictionRanges.fit(pd.DataFrame(), 8).evidence["status"]
        == "insufficient_evidence"
    )


def test_fixed_policy_chooses_forecast_not_actual_and_preserves_negative_points():
    players = pd.DataFrame({"player_id": ["a", "b"], "pos": ["RB", "RB"]})
    projections = pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "week": [10, 10],
            "status": ["projected"] * 2,
            "projected_points": [-2, -5],
        }
    )
    plan = planned_lineup(
        players, projections, {"RB": ["RB"]}, {"a", "b"}, [10], {"a": 1, "b": 1}
    )
    assert plan == {"expected": -2, "selections": [("a", 10)]}
    assert exposure(plan, plan) == 0
    projections.loc[0, "status"] = "unknown"
    assert (
        planned_lineup(
            players, projections, {"RB": ["RB"]}, {"a", "b"}, [10], {"a": 1, "b": 1}
        )
        is None
    )


def test_shared_players_cancel_and_noop_has_no_fabricated_probability():
    before = {"selections": [("shared", 10), ("out", 10)]}
    after = {"selections": [("shared", 10), ("in", 10)]}
    assert exposure(before, after) == 2
    m = TradePredictionRanges.fit(records(), 8)
    result = m.apply(0, 8, 0)
    assert result["prediction_lower"] == result["prediction_upper"] == 0
    assert result["probability_positive"] is None


def test_json_replay_preserves_interval_and_nonfinite_evidence_rejected():
    m = TradePredictionRanges.fit(records(), 8)
    loaded = TradePredictionRanges(json.loads(json.dumps(m.evidence)))
    assert m.apply(5, 8, 16) == loaded.apply(5, 8, 16)
    bad = records()
    bad.loc[0, "actual"] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        TradePredictionRanges.fit(bad, 8)


def test_probability_withheld_when_it_does_not_beat_calibration_only_base_rate():
    data = records()
    data["actual"] = data.expected + 1
    m = TradePredictionRanges.fit(data, 8)
    assert not m.evidence["probability_available"]
    assert m.apply(5, 8, 16)["probability_positive"] is None


class Predictor:
    def fit(self, history):
        self.cutoff = history.period.max()
        return self

    def predict(self, fixtures):
        assert (fixtures.season * 100 + fixtures.week > self.cutoff).all()
        assert set(fixtures.columns) == {
            "player_id",
            "player_name",
            "pos",
            "season",
            "week",
            "opp",
        }
        return fixtures.assign(projected_points=fixtures.player_id.astype(int) + 1)


def test_replay_freezes_origin_forecasts_and_uses_complete_schedule_coverage():
    history = pd.DataFrame(
        [
            {
                "player_id": str(p),
                "player_name": str(p),
                "pos": "RB" if p % 2 else "WR",
                "team": "AAA" if p % 2 else "BBB",
                "opp": "BBB" if p % 2 else "AAA",
                "season": season,
                "week": week,
                "period": season * 100 + week,
                "fantasy_points": float(p + week),
            }
            for season in [2023, 2024, 2025, 2026]
            for week in range(1, 18)
            for p in range(12)
        ]
    )
    schedule = pd.DataFrame(
        [
            {
                "season": s,
                "week": w,
                "game_type": "REG",
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": 20,
                "away_score": 10,
            }
            for s in [2023, 2024, 2025, 2026]
            for w in range(1, 18)
        ]
    )
    slots = {"RB": ["RB"], "WR": ["WR"]}
    a = replay_trades(
        history, schedule, slots, 8, teams=2, model_factory=Predictor, trials=2
    )
    changed = history.copy()
    changed.loc[changed.period.ge(202405), "fantasy_points"] *= 100
    b = replay_trades(
        changed, schedule, slots, 8, teams=2, model_factory=Predictor, trials=2
    )
    assert not a.empty
    assert (
        a.loc[a.origin.eq(202405), "expected"].tolist()
        == b.loc[b.origin.eq(202405), "expected"].tolist()
    )
    assert (
        a.loc[a.origin.eq(202405), "actual"].tolist()
        != b.loc[b.origin.eq(202405), "actual"].tolist()
    )
    broken = schedule.copy()
    broken["home_score"] = np.nan
    assert replay_trades(
        history, broken, slots, 8, teams=2, model_factory=Predictor, trials=2
    ).empty


def test_pick_and_multi_player_offers_do_not_inherit_one_for_one_validation():
    from types import SimpleNamespace

    m = TradePredictionRanges.fit(records(), 8)
    result = {
        "give": ["a"],
        "receive": ["b"],
        "my_drops": [],
        "partner_drops": [],
        "give_picks": [{"pick_id": "2027:1:1"}],
        "receive_picks": [],
    }
    assert m.assess(SimpleNamespace(), 1, 2, result)["status"] == "unavailable"
    result["give_picks"] = []
    result["give"] = ["a", "c"]
    assert m.assess(SimpleNamespace(), 1, 2, result)["status"] == "unavailable"


def test_email_labels_policy_coverage_and_separates_keeper_scenarios():
    from fantasyfootball.reports.trades import render_trades

    m = TradePredictionRanges.fit(records(), 8)
    interval = m.apply(10, 8, 16)
    report = {
        "season": 2026,
        "week": 10,
        "weeks": [10, 11],
        "status": "estimated",
        "as_of": "2026-11-11",
        "players": {
            "a": {"name": "A", "pos": "RB", "team": "AAA"},
            "b": {"name": "B", "pos": "WR", "team": "BBB"},
        },
        "opportunities": [
            {
                "partner_roster": 2,
                "give": ["a"],
                "receive": ["b"],
                "my_gain": 10,
                "partner_gain": 5,
                "weekly": [
                    {
                        "week": 10,
                        "my_gain": 10,
                        "partner_gain": 5,
                        "my_after": {"filled": 1, "slots": 1},
                    }
                ],
                "uncertainty": {"status": "estimated", "you": interval},
            }
        ],
        "uncertainty_validation": m.evidence,
    }
    _, plain, html = render_trades(report, "Team")
    assert (
        "Nominal 80% prediction interval" in plain
        and "Nominal 80% prediction interval" in html
    )
    assert (
        "fixes weekly starters" in plain
        and "overlapping historical forecast windows" in plain
    )
    assert "not a confidence interval" in plain


def test_missing_weekly_waiver_alternative_is_optional_but_owned_player_is_not():
    players = pd.DataFrame({"player_id": ["a", "waiver"], "pos": ["RB", "RB"]})
    projections = pd.DataFrame(
        {
            "player_id": ["a"],
            "week": [10],
            "status": ["projected"],
            "projected_points": [10],
        }
    )
    args = (
        players,
        projections,
        {"RB": ["RB"]},
        {"a", "waiver"},
        [10],
        {"a": 1, "waiver": 1},
    )
    assert planned_lineup(*args, optional_ids={"waiver"})["expected"] == 10
    assert planned_lineup(*args) is None
