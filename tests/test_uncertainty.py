from typing import ClassVar

import pandas as pd
import pytest

from fantasyfootball.forecasting.uncertainty import RollingErrorRanges
from fantasyfootball.reports.reporting import render_ranges


def history():
    return pd.DataFrame(
        [
            {
                "player_id": str(i),
                "player_name": f"P{i}",
                "pos": "RB",
                "season": 2026,
                "week": week,
                "period": 202600 + week,
                "opp": "NE",
                "fantasy_points": float(i + week),
            }
            for week in range(1, 11)
            for i in range(4)
        ]
    )


class Predictor:
    fits: ClassVar[list] = []

    def fit(self, data):
        self.cutoff = data.period.max()
        self.fits.append(self.cutoff)
        return self

    def predict(self, fixtures):
        assert (fixtures.season * 100 + fixtures.week > self.cutoff).all()
        result = fixtures.copy()
        result["history_games"] = 5
        result["projected_points"] = 10.0
        return result


def ranges(data=None):
    return RollingErrorRanges(
        calibration_weeks=3, validation_weeks=2, min_samples=4, model_factory=Predictor
    ).fit(history() if data is None else data)


def test_ranges_use_only_prior_week_models_and_disjoint_validation():
    Predictor.fits = []
    model = ranges()
    assert Predictor.fits == [202605, 202606, 202607, 202608, 202609]
    assert model.report["calibration_periods"] == [202606, 202607, 202608]
    assert model.report["validation_periods"] == [202609, 202610]
    assert model.report["positions"]["RB"]["calibration_rows"] == 12
    assert model.report["positions"]["RB"]["validation_rows"] == 8


def test_validation_outcomes_do_not_change_range_width():
    before = ranges()
    changed = history()
    changed.loc[changed.week >= 9, "fantasy_points"] = 10000
    after = ranges(changed)
    assert before.widths == after.widths
    assert after.report["positions"]["RB"]["observed_coverage"] == 0


def test_unknown_position_and_cold_start_have_no_fabricated_interval():
    frame = pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "pos": ["RB", "QB", "RB"],
            "season": [2026] * 3,
            "week": [11] * 3,
            "history_games": [8, 8, 0],
            "projected_points": [10.0] * 3,
        }
    )
    result = ranges().apply(frame)
    assert result.prediction_lower.iloc[0] <= 10 <= result.prediction_upper.iloc[0]
    assert result.prediction_lower.iloc[1:].isna().all()
    assert result.range_status.tolist() == [
        "estimated",
        "insufficient_evidence",
        "insufficient_evidence",
    ]
    with pytest.raises(ValueError, match="after"):
        ranges().apply(frame.assign(week=10))


def test_insufficient_history_returns_unavailable():
    model = ranges(history().loc[lambda d: d.week <= 2])
    assert not model.widths
    assert model.report["status"] == "insufficient_history"


def test_visual_is_email_safe_and_does_not_invent_certainty():
    board = pd.DataFrame(
        {
            "player_id": ["a"],
            "player_name": ["<script>"],
            "pos": ["RB"],
            "prediction_lower": [-2.0],
            "prediction_upper": [20.0],
            "projected_points": [9.0],
        }
    )
    html = render_ranges(
        board,
        {"a"},
        {
            "target_coverage": 0.8,
            "positions": {"RB": {"observed_coverage": 0.75, "validation_rows": 20}},
        },
    )
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "75% of 20" in html and "-2.0 to 20.0" in html
    assert "80% target" in html and "not confidence intervals" in html
    assert "<svg" not in html and "<img" not in html
    assert "unavailable" in render_ranges(board.iloc[:0], set(), {})


def test_nested_ranges_use_separate_error_quantiles():
    model = ranges()
    # Calibration errors: [4,3,2,1, 3,2,1,0, 2,1,0,1].
    # Finite-sample ranks ceil(13 * coverage): rank 7 = 2, rank 11 = 3.
    assert model.inner_widths["RB"] == 2
    assert model.widths["RB"] == 3
    assert model.report["positions"]["RB"]["observed_inner_coverage"] == 0.875
    assert model.report["positions"]["RB"]["observed_coverage"] == 1.0
    changed = history()
    changed.loc[changed.week >= 9, "fantasy_points"] = 10000
    after = ranges(changed)
    assert after.inner_widths == model.inner_widths
    assert after.report["positions"]["RB"]["observed_inner_coverage"] == 0
    frame = pd.DataFrame(
        {
            "pos": ["RB", "QB", "RB"],
            "season": [2026] * 3,
            "week": [11] * 3,
            "history_games": [8, 8, 0],
            "projected_points": [1.0] * 3,
        }
    )
    result = model.apply(frame)
    assert result.prediction_inner_lower.iloc[0] == -1
    assert result.prediction_inner_upper.iloc[0] == 3
    assert result.prediction_inner_lower.iloc[1:].isna().all()
    assert result.range_inner_target_coverage.eq(0.5).all()


def test_nested_chart_labels_and_invalid_inner_fallback():
    board = pd.DataFrame(
        {
            "player_id": ["a"],
            "player_name": ["A"],
            "pos": ["RB"],
            "projected_points": [10.0],
            "prediction_lower": [-2.0],
            "prediction_upper": [22.0],
            "prediction_inner_lower": [5.0],
            "prediction_inner_upper": [15.0],
        }
    )
    html = render_ranges(
        board, {"a"}, {"target_coverage": 0.8, "inner_target_coverage": 0.5}
    )
    assert "50% / 80% target" in html
    assert "50%: 5.0 to 15.0" in html and "80%: -2.0 to 22.0" in html
    assert "height:18px" in html and "height:8px" in html
    assert "not a statistical significance test" in html
    board.loc[0, "prediction_inner_upper"] = 30
    assert "Inner range unavailable" in render_ranges(board, set(), {})


def test_invalid_nested_coverage_rejected():
    with pytest.raises(ValueError, match="configuration"):
        RollingErrorRanges(inner_coverage=0.9, coverage=0.8)
