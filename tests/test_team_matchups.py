import pandas as pd
import pytest

from fantasyfootball.reports.visualization import PlotlyVisualizer
from fantasyfootball.research.matchups import TeamMatchups


def fixture():
    return pd.DataFrame(
        {
            "game_id": ["g1"] * 4 + ["g2"] * 2,
            "play_id": list(range(6)),
            "season": [2026] * 6,
            "week": [1] * 4 + [2] * 2,
            "season_type": ["REG"] * 6,
            "posteam": ["A"] * 6,
            "defteam": ["B"] * 6,
            "play_type": ["pass", "pass", "run", "run", "pass", "run"],
            "two_point_attempt": [0] * 6,
            "qb_dropback": [1, 1, 0, 1, 1, 0],
            "rush_attempt": [0, 0, 1, 1, 0, 1],
            "qb_kneel": [0] * 6,
            "qb_spike": [0] * 6,
            "epa": [1.0, -2.0, 0.5, 0.2, 100.0, 100.0],
            "sack": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        }
    )


def test_shared_denominators_scrambles_and_cutoff():
    service = TeamMatchups()
    summary = service.summarize(fixture(), season=2026, through_week=1)
    comparison = service.compare(summary, offense="A", defense="B")
    for unit in ["Offense", "Defense"]:
        rows = comparison.loc[comparison.unit.eq(unit)].set_index("metric")
        assert rows.loc["Dropback EPA", "value"] == pytest.approx(-0.8 / 3)
        assert rows.loc["Sack rate", "value"] == pytest.approx(1 / 3)
        assert rows.loc["Rush EPA", "observations"] == 1
        assert rows.loc["Rush EPA", "value"] == 0.5
    assert len(comparison) == 6


def test_missing_outcomes_retain_eligible_counts():
    source = fixture()
    source.loc[:1, "epa"] = float("nan")
    source.loc[3, "epa"] = float("nan")
    rows = TeamMatchups().summarize(source, season=2026, through_week=1)
    passing = rows.loc[rows.metric.eq("Dropback EPA")]
    assert passing.value.isna().all()
    assert passing.observations.eq(0).all() and passing.eligible_plays.eq(3).all()
    figure = PlotlyVisualizer().team_matchup(rows, "Dropback EPA")
    assert "no observed values" in figure.layout.annotations[0].text


def test_invalid_and_excluded_plays():
    source = fixture()
    with pytest.raises(ValueError, match="Unique"):
        TeamMatchups().summarize(
            pd.concat([source, source]), season=2026, through_week=1
        )
    source.loc[0, "two_point_attempt"] = 1
    source.loc[1, "qb_spike"] = 1
    source.loc[2, "qb_kneel"] = 1
    source.loc[3, "play_type"] = "no_play"
    assert TeamMatchups().summarize(source, season=2026, through_week=1).empty


def test_comparison_rejects_mixed_cutoffs_and_missing_team():
    service = TeamMatchups()
    rows = service.summarize(fixture(), season=2026, through_week=1)
    with pytest.raises(ValueError, match="Both"):
        service.compare(rows, offense="C", defense="B")
    rows.loc[0, "through_week"] = 2
    with pytest.raises(ValueError, match="one season"):
        service.compare(rows, offense="A", defense="B")


def test_sack_chart_units_and_zero_axis():
    rows = TeamMatchups().summarize(fixture(), season=2026, through_week=1)
    figure = PlotlyVisualizer().team_matchup(rows, "Sack rate")
    assert figure.layout.yaxis.tickformat == ".0%"
    assert figure.layout.yaxis.rangemode == "tozero"
    assert figure.data[0].x[0] == "A sacks conceded"
