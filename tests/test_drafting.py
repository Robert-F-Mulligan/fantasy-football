import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from fantasyfootball.domain import LeagueSettings, ScoringRules
from fantasyfootball.drafting import (
    DraftService,
    ADPAvailability,
    GapTiers,
    next_snake_pick,
)
from fantasyfootball.projections import WeightedHistoryModel, WalkForwardEvaluator
from fantasyfootball.application import DraftApplication


@pytest.fixture
def pool():
    return pd.DataFrame(
        {
            "player_id": list("abcdef"),
            "player_name": list("ABCDEF"),
            "pos": ["RB"] * 3 + ["WR"] * 3,
            "projected_points": [300, 260, 100, 290, 200, 90],
            "adp": [1, 2, 6, 3, 4, 5],
            "adp_std": [2.0] * 6,
        }
    )


@pytest.fixture
def league():
    return LeagueSettings(teams=1, starters={"RB": 1, "WR": 1}, flex=1)


def test_flex_replacement_and_drafted_filter(pool, league):
    original = pool.copy(deep=True)
    board = DraftService(league).rank(pool, drafted=["a"], pick=2, next_pick=4)
    assert board.player_id.tolist() == ["b", "d", "e", "c", "f"]
    assert dict(board.groupby("pos").replacement_points.first()) == {
        "RB": 100,
        "WR": 200,
    }
    assert board.loc[board.player_id == "b", "value_over_replacement"].iloc[0] == 160
    assert_frame_equal(pool, original)


@pytest.mark.parametrize(
    "column,value",
    [
        ("projected_points", np.nan),
        ("projected_points", np.inf),
        ("adp", -1),
        ("adp_std", 0),
    ],
)
def test_invalid_values_fail(pool, league, column, value):
    pool[column] = pool[column].astype(float)
    pool.loc[0, column] = value
    with pytest.raises(ValueError):
        DraftService(league).rank(pool)


def test_duplicate_ids_fail(pool, league):
    pool.loc[1, "player_id"] = "a"
    with pytest.raises(ValueError, match="unique"):
        DraftService(league).rank(pool)


def test_insufficient_depth_fails(pool):
    with pytest.raises(ValueError, match="depth"):
        DraftService(
            LeagueSettings(teams=10, starters={"RB": 2, "WR": 2}, flex=0)
        ).rank(pool)


def test_missing_position_fails(pool, league):
    with pytest.raises(ValueError, match="Missing starting"):
        DraftService(league).rank(pool[pool.pos == "RB"])


def test_missing_adp_stays_unknown(pool, league):
    result = DraftService(league).rank(pool.drop(columns=["adp", "adp_std"]))
    assert result.available_next_pick.isna().all()


def test_availability_is_conditional_and_monotonic():
    model = ADPAvailability()
    assert model.probability(20, 5, 10, 10) == 1
    assert 0 < model.probability(20, 5, 30, 10) < model.probability(20, 5, 20, 10) < 1
    assert model.probability(20, 5, 30, 20) > model.probability(20, 5, 30, 10)
    with pytest.raises(ValueError):
        model.probability(20, 5, 5, 10)


@pytest.mark.parametrize("pick,expected", [(1, 24), (12, 13), (13, 36), (24, 25)])
def test_snake_pick(pick, expected):
    assert next_snake_pick(pick, 12) == expected


def test_ties_same_tier(pool):
    pool.loc[:2, "projected_points"] = 100
    assert GapTiers().assign(pool).iloc[:3].tolist() == [1, 1, 1]


def test_scoring_requires_explicit_stats():
    rules = ScoringRules({"receiving_rec": 0.5, "receiving_yds": 0.1})
    assert (
        rules.score(pd.DataFrame({"receiving_rec": [10], "receiving_yds": [100]})).iloc[
            0
        ]
        == 15
    )
    with pytest.raises(ValueError, match="Missing columns"):
        rules.score(pd.DataFrame({"receiving_rec": [10]}))


def history():
    return pd.DataFrame(
        [
            {
                "player_id": p,
                "player_name": p,
                "pos": "RB",
                "season": y,
                "games": 10,
                "fantasy_points": pts,
            }
            for y, pts in [(2021, 100), (2022, 200), (2023, 300)]
            for p in ["a", "b"]
        ]
    )


def test_predictions_exclude_target_and_future():
    data = history()
    model = WeightedHistoryModel(prior_games=0, season_games=10)
    before = model.predict(data, 2023)
    data.loc[data.season == 2023, "fantasy_points"] = 999999
    assert_frame_equal(before, model.predict(data, 2023))
    assert before.projected_points.iloc[0] == pytest.approx(162.5)


def test_evaluator_never_passes_future_to_model():
    class Spy(WeightedHistoryModel):
        def predict(self, data, season):
            assert (data.season < season).all()
            return super().predict(data, season)

    result = WalkForwardEvaluator(Spy()).evaluate(history())
    assert result.season.tolist() == [2022, 2023]
    assert result.coverage.tolist() == [1.0, 1.0]
    assert (result.mae >= 0).all()


def test_duplicate_history_fails():
    data = history()
    with pytest.raises(ValueError, match="one row"):
        WeightedHistoryModel().predict(pd.concat([data, data.iloc[:1]]), 2024)


def test_adp_join_preserves_string_ids(pool, league):
    market = pool[["player_id", "adp", "adp_std"]].copy()
    result = DraftApplication(league).prepare(
        pool.drop(columns=["adp", "adp_std"]), adp=market
    )
    assert result.adp.notna().all()
    with pytest.raises(ValueError, match="unique"):
        DraftApplication(league).prepare(pool, adp=pd.concat([market, market.iloc[:1]]))


def test_weekly_history_adapter():
    from fantasyfootball.adapters import WeeklyHistoryAdapter

    weekly = pd.DataFrame(
        {
            "player_id": ["01", "01"],
            "player_name": ["A", "A"],
            "pos": ["RB", "RB"],
            "year": [2023, 2023],
            "week": [1, 2],
            "rushing_yds": [100, 50],
        }
    )
    result = WeeklyHistoryAdapter(ScoringRules({"rushing_yds": 0.1})).transform(weekly)
    assert result.fantasy_points.tolist() == [15.0]
    assert result.games.tolist() == [2]
    assert result.player_id.tolist() == ["01"]
    with pytest.raises(ValueError, match="Duplicate"):
        WeeklyHistoryAdapter(ScoringRules({"rushing_yds": 0.1})).transform(
            pd.concat([weekly, weekly])
        )


@pytest.mark.parametrize("passing_td_points", [4, 6])
def test_fantasypros_transformer_to_league_draft(passing_td_points):
    from fantasyfootball.transformers.fantasypros_transformer import (
        ProjectionsTransfomer,
    )

    raw = pd.DataFrame(
        {
            "player_id": ["fp:1", "fp:2"],
            "player": ["Alpha BUF", "Beta NYJ"],
            "pos": ["QB", "QB"],
            "passing_yds": [4000, 3000],
            "passing_tds": [30, 20],
            "passing_ints": [10, 5],
            "rushing_yds": [200, 100],
            "rushing_tds": [2, 1],
            "misc_fl": [1, 0],
            "misc_fpts": [999, 999],
        }
    )
    projections = ProjectionsTransfomer().transform(raw)
    original = projections.copy(deep=True)
    weights = dict(ScoringRules().weights)
    weights["passing_td"] = passing_td_points
    league = LeagueSettings(
        teams=1, starters={"QB": 1}, flex=0, scoring=ScoringRules(weights)
    )
    result = DraftApplication(league).prepare(projections).set_index("player_id")
    assert result.loc["fp:1", "projected_points"] == pytest.approx(
        170 + 30 * passing_td_points
    )
    assert result.loc["fp:2", "projected_points"] == pytest.approx(
        126 + 20 * passing_td_points
    )
    assert result.loc["fp:1", "projected_fantasy_points"] == 999
    assert_frame_equal(projections, original)


def test_fantasypros_alias_collision_is_explicit():
    from fantasyfootball.adapters import FantasyProsProjectionAdapter

    with pytest.raises(ValueError, match="Ambiguous"):
        FantasyProsProjectionAdapter().transform(
            pd.DataFrame({"passing_td": [1], "passing_tds": [2]})
        )
