import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from fantasyfootball.features import (
    WeeklyFeatures,
    SeasonFeatures,
    prepare_weekly,
    STATS,
)
from fantasyfootball.models import FactorModel
from fantasyfootball.optimization import LineupOptimizer
from fantasyfootball.domain import ScoringRules


def history():
    rows = []
    for year in range(2019, 2024):
        for week in range(1, 5):
            for i in range(8):
                rows.append(
                    dict(
                        player_id=str(i),
                        player_name=f"Player {i}",
                        pos="RB",
                        season=year,
                        week=week,
                        opp="ABC" if i % 2 else "XYZ",
                        age=25 + year - 2019,
                        **{s: float(i + week) for s in STATS},
                    )
                )
    return prepare_weekly(pd.DataFrame(rows), ScoringRules({"rushing_yds": 0.1}))


def test_weekly_current_and_future_stats_cannot_affect_features():
    data = history()
    before, cols = WeeklyFeatures().build(data)
    changed = data.copy()
    changed.loc[changed.period >= 202203, STATS + ["fantasy_points", "age"]] = 99999
    after, _ = WeeklyFeatures().build(changed)
    assert_frame_equal(
        before.loc[before.period <= 202203, cols],
        after.loc[after.period <= 202203, cols],
    )


def test_season_target_and_future_stats_cannot_affect_features():
    data = history()
    before, cols = SeasonFeatures().build(data)
    changed = data.copy()
    changed.loc[changed.season >= 2022, STATS + ["fantasy_points", "age"]] = 99999
    after, _ = SeasonFeatures().build(changed)
    assert_frame_equal(
        before.loc[before.season <= 2022, cols], after.loc[after.season <= 2022, cols]
    )


def test_fixture_predictions_ignore_supplied_outcomes():
    data = history()
    fixtures = pd.DataFrame(
        {
            "player_id": ["0"],
            "player_name": ["P"],
            "pos": ["RB"],
            "season": [2024],
            "week": [1],
            "opp": ["ABC"],
        }
    )
    before, cols = WeeklyFeatures().build(data, fixtures)
    fixtures["fantasy_points"] = 99999
    fixtures["rushing_att"] = 99999
    after, _ = WeeklyFeatures().build(data, fixtures)
    assert_frame_equal(before[cols], after[cols])


def test_forecast_rejects_past_week():
    data = history()
    fixtures = data.iloc[:1].copy()
    with pytest.raises(ValueError, match="strictly after"):
        WeeklyFeatures().build(data, fixtures)


def test_factor_model_fit_predict():
    data = history()
    model = FactorModel("season", min_samples=10).fit(data)
    result = model.predict(season=2024)
    assert len(result) == 8
    assert np.isfinite(result.projected_points).all()


def test_weekly_cold_start_explicit_history_count():
    data = history()
    model = FactorModel("weekly", min_samples=10).fit(data)
    fixtures = pd.DataFrame(
        {
            "player_id": ["new"],
            "player_name": ["New"],
            "pos": ["RB"],
            "season": [2024],
            "week": [1],
            "opp": ["ABC"],
        }
    )
    result = model.predict(fixtures=fixtures)
    assert result.history_games.iloc[0] == 0


def test_lineup_uses_unique_players_and_flex():
    pool = pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "d"],
            "player_name": list("ABCD"),
            "pos": ["RB", "RB", "WR", "TE"],
            "projected_points": [20, 19, 18, 30],
        }
    )
    lineup = LineupOptimizer().optimize(
        pool, {"RB": ["RB"], "WR": ["WR"], "FLEX": ["RB", "WR", "TE"]}
    )
    assert set(lineup.player_id) == {"a", "c", "d"}
    locked = LineupOptimizer().optimize(
        pool, {"RB": ["RB"], "FLEX": ["RB", "WR", "TE"]}, locked=["b"]
    )
    assert set(locked.player_id) == {"b", "d"}
    with pytest.raises(ValueError):
        LineupOptimizer().optimize(pool, {"QB": ["QB"]})
    with pytest.raises(ValueError):
        LineupOptimizer().optimize(pool, {"RB": ["RB"]}, locked=["c"])


def test_excluded_players_cannot_start():
    pool = pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "player_name": ["A", "B"],
            "pos": ["RB", "RB"],
            "projected_points": [20, 10],
        }
    )
    assert LineupOptimizer().optimize(
        pool, {"RB": ["RB"]}, excluded=["a"]
    ).player_id.tolist() == ["b"]


def test_public_fantasypros_report_receptions():
    import json
    from fantasyfootball.datasources.fantasypros import FantasyProsDatasource
    from fantasyfootball.parsers.html_parser import HTMLParser

    report = {
        "type": "nfl_projections",
        "table": {
            "rows": [
                {
                    "player": {"id": 12, "name": "A", "team": "NYJ"},
                    "rec_att": 40,
                    "rec_yds": 300,
                }
            ]
        },
    }
    parser = HTMLParser()
    parser.set_content(
        "<script>window.FP.reportConfig = " + json.dumps(report) + ";</script>"
    )
    parser.parse()
    frame = FantasyProsDatasource(parser=parser)._public_report_projections()
    assert frame.receiving_rec.iloc[0] == 40
    assert frame.player_id.iloc[0] == "fp:12"


def test_season_target_position_does_not_leak():
    data = history()
    before, cols = SeasonFeatures().build(data)
    changed = data.copy()
    changed.loc[changed.season == 2023, "pos"] = "QB"
    after, _ = SeasonFeatures().build(changed)
    assert_frame_equal(
        before.loc[before.season == 2023, cols], after.loc[after.season == 2023, cols]
    )


def test_projection_metadata_remains_missing_not_zero():
    from fantasyfootball.transformers.fantasypros_transformer import (
        ProjectionsTransfomer,
    )

    raw = pd.DataFrame(
        {
            "player": ["A NYJ"],
            "player_id": ["fp:1"],
            "pos": ["RB"],
            "rushing_yds": [100.0],
        }
    )
    result = ProjectionsTransfomer().transform(raw)
    assert pd.isna(result.as_of_date.iloc[0])
    assert result.receiving_rec.iloc[0] == 0
    assert "passing_att" not in raw
