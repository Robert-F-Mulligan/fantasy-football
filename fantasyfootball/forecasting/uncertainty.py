"""Empirical weekly error ranges from chronological out-of-sample forecasts.

These are nominal prediction ranges, not confidence intervals or guaranteed
player-specific probabilities. Position-level widths are checked on later weeks.
"""

import math

import numpy as np
import pandas as pd

from fantasyfootball.forecasting.models import FactorModel


class RollingErrorRanges:
    def __init__(
        self,
        coverage=0.8,
        calibration_weeks=6,
        validation_weeks=2,
        min_samples=30,
        min_history_games=4,
        model_factory=None,
    ):
        if (
            not 0 < coverage < 1
            or min(calibration_weeks, validation_weeks, min_samples, min_history_games)
            < 1
        ):
            raise ValueError("Invalid error-range configuration")
        self.coverage = coverage
        self.calibration_weeks = calibration_weeks
        self.validation_weeks = validation_weeks
        self.min_samples = min_samples
        self.min_history_games = min_history_games
        self.model_factory = model_factory or (lambda: FactorModel("weekly"))
        self.widths = {}
        self.report = {}

    def fit(self, history):
        self.widths = {}
        periods = sorted(history.period.unique())
        required = self.calibration_weeks + self.validation_weeks
        self.cutoff = int(history.period.max())
        self.report = {
            "target_coverage": self.coverage,
            "method": "position-level rolling-origin absolute errors",
            "history_cutoff": self.cutoff,
            "positions": {},
            "status": "insufficient_history",
            "limitations": "Observed player-games only; excludes DNPs. Temporal dependence and changing models mean coverage is not guaranteed.",
        }
        if len(periods) <= required:
            return self
        selected = periods[-required:]
        records = []
        for period in selected:
            train = history.loc[history.period < period]
            observed = history.loc[history.period == period]
            model = self.model_factory()
            try:
                model.fit(train)
            except ValueError as exc:
                # The default estimator has an explicit minimum training sample size.
                if str(exc).startswith("Need at least "):
                    return self
                raise
            prediction = model.predict(
                fixtures=observed[
                    ["player_id", "player_name", "pos", "season", "week", "opp"]
                ]
            )
            merged = prediction.merge(
                observed[["player_id", "fantasy_points"]],
                on="player_id",
                validate="one_to_one",
            )
            merged = merged.loc[merged.history_games >= self.min_history_games].copy()
            merged["error"] = (merged.projected_points - merged.fantasy_points).abs()
            merged["period"] = int(period)
            records.append(merged[["pos", "period", "error"]])
        errors = pd.concat(records, ignore_index=True)
        calibration_periods = selected[: self.calibration_weeks]
        validation_periods = selected[self.calibration_weeks :]
        calibration = errors.loc[errors.period.isin(calibration_periods)]
        validation = errors.loc[errors.period.isin(validation_periods)]
        for position, group in calibration.groupby("pos"):
            values = group.error.to_numpy()
            if len(values) < self.min_samples:
                continue
            rank = math.ceil((len(values) + 1) * self.coverage)
            if rank > len(values):
                continue
            width = float(np.sort(values)[rank - 1])
            check = validation.loc[validation.pos == position, "error"]
            self.widths[position] = width
            self.report["positions"][position] = {
                "half_width": width,
                "calibration_rows": len(values),
                "validation_rows": len(check),
                "observed_coverage": float(check.le(width).mean())
                if len(check)
                else None,
            }
        self.report.update(
            status="estimated" if self.widths else "insufficient_samples",
            calibration_periods=[int(p) for p in calibration_periods],
            validation_periods=[int(p) for p in validation_periods],
        )
        return self

    def apply(self, predictions):
        if not hasattr(self, "cutoff"):
            raise ValueError("Fit ranges before applying them")
        if not ((predictions.season * 100 + predictions.week) > self.cutoff).all():
            raise ValueError("Range predictions must be after calibration history")
        result = predictions.copy()
        width = result.pos.map(self.widths)
        enough = result.history_games >= self.min_history_games
        width = width.where(enough)
        result["prediction_lower"] = result.projected_points - width
        result["prediction_upper"] = result.projected_points + width
        result["range_target_coverage"] = self.coverage
        result["range_status"] = np.where(
            width.notna(), "estimated", "insufficient_evidence"
        )
        return result
