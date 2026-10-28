import pandas as pd
import pytest

from fantasyfootball.reports.visualization import PlotlyVisualizer
from fantasyfootball.research.tendencies import NeutralTendencies


def fixture():
    return pd.DataFrame(
        {
            "game_id": ["g"] * 7,
            "play_id": list(range(7)),
            "season": [2026] * 7,
            "week": [1] * 7,
            "season_type": ["REG"] * 7,
            "posteam": ["A"] * 6 + ["B"],
            "play_type": ["pass", "run", "run", "pass", "pass", "pass", "run"],
            "two_point_attempt": [0] * 7,
            "qb_kneel": [0] * 7,
            "qb_spike": [0] * 7,
            "qb_dropback": [1, 1, 0, 1, 1, 1, 0],
            "rush_attempt": [0, 1, 1, 0, 0, 0, 1],
            "down": [1, 2, 2, 1, 3, 1, 3],
            "half_seconds_remaining": [121, 300, 400, 120, 300, 300, 300],
            "wp": [0.2, 0.8, 0.5, 0.5, 0.5, None, 0.5],
        }
    )


def test_boundaries_scrambles_and_coverage():
    result = (
        NeutralTendencies()
        .summarize(fixture(), season=2026, through_week=1)
        .set_index("team")
    )
    assert result.loc["A", "dropback_rate"] == pytest.approx(2 / 3)
    assert result.loc["A", "neutral_plays"] == 3
    assert result.loc["A", "incomplete_context"] == 1
    assert result.loc["A", "eligible_plays"] == 6
    assert pd.isna(result.loc["B", "dropback_rate"])


def test_excluded_and_future_plays():
    data = fixture()
    data.loc[0, "two_point_attempt"] = 1
    data.loc[1, "qb_spike"] = 1
    data.loc[2, "week"] = 2
    result = NeutralTendencies().summarize(data, season=2026, through_week=1)
    assert result.neutral_plays.eq(0).all()


def test_invalid_probability_and_duplicate_plays():
    data = fixture()
    with pytest.raises(ValueError, match="Unique"):
        NeutralTendencies().summarize(
            pd.concat([data, data]), season=2026, through_week=1
        )
    data.loc[0, "wp"] = 2
    with pytest.raises(ValueError, match="wp"):
        NeutralTendencies().summarize(data, season=2026, through_week=1)


def test_chart_omits_unknown_rate_without_inventing_zero():
    data = NeutralTendencies().summarize(fixture(), season=2026, through_week=1)
    figure = PlotlyVisualizer().neutral_tendencies(data)
    assert list(figure.data[0].y) == ["A"]
    assert figure.layout.xaxis.range == (0, 1)
    assert "1 teams" in figure.layout.annotations[0].text
