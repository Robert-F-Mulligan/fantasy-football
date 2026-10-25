from typing import ClassVar

import pandas as pd
import pytest

from fantasyfootball.reporting import render_ranges
from fantasyfootball.uncertainty import RollingErrorRanges


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
