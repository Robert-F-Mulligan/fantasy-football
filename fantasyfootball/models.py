"""Boosted-tree forecasts with chronological holdouts and baseline comparisons."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from .features import WeeklyFeatures, SeasonFeatures


class FactorModel:
    def __init__(self, horizon="weekly", min_samples=100):
        if horizon not in ("weekly", "season"):
            raise ValueError("horizon must be weekly or season")
        self.horizon = horizon
        self.features = WeeklyFeatures() if horizon == "weekly" else SeasonFeatures()
        self.min_samples = min_samples
        self.estimator = None

    def _estimator(self):
        # Disable random early-stopping splits: model selection is chronological.
        return HistGradientBoostingRegressor(
            max_iter=120,
            max_leaf_nodes=15,
            learning_rate=0.06,
            l2_regularization=10,
            min_samples_leaf=25,
            early_stopping=False,
            random_state=42,
        )

    def fit(self, history):
        data, self.columns = self.features.build(history)
        if self.horizon == "weekly":
            data = data[data.previous_games > 0]
        if len(data) < self.min_samples:
            raise ValueError(
                f"Need at least {self.min_samples} historical training rows"
            )
        self.estimator = self._estimator()
        self.estimator.fit(data[self.columns], data.fantasy_points)
        self.cutoff = int(history.period.max())
        self.history = history.copy()
        return self

    def predict(self, *, fixtures=None, season=None):
        if self.estimator is None:
            raise ValueError("Fit the model before predicting")
        if self.horizon == "weekly":
            if fixtures is None:
                raise ValueError("Weekly forecasts require scheduled fixtures")
            data, cols = self.features.build(self.history, fixtures=fixtures)
        else:
            if season is None:
                raise ValueError("Season forecast requires target season")
            data, cols = self.features.build(self.history, season=season)
        if data.empty:
            raise ValueError("No eligible forecast rows")
        result = data[["player_id", "player_name", "pos", "season"]].copy()
        if self.horizon == "weekly":
            result["week"] = data.week
            result["opp"] = data.opp
            result["history_games"] = data.previous_games
        result["projected_points"] = self.estimator.predict(data[self.columns])
        return result.reset_index(drop=True)

    def evaluate(self, history, holdouts=None):
        data, cols = self.features.build(history)
        if self.horizon == "weekly":
            data = data[data.previous_games > 0]
        seasons = sorted(data.season.unique())
        holdouts = holdouts if holdouts is not None else seasons[2:]
        records = []
        for season in holdouts:
            train = data[data.season < season]
            test = data[data.season == season]
            if len(train) < self.min_samples or test.empty:
                continue
            estimator = self._estimator().fit(train[cols], train.fantasy_points)
            prediction = estimator.predict(test[cols])
            baseline = (
                test.prior4_fantasy_points
                if self.horizon == "weekly"
                else test.previous_fantasy_points
            )
            error = prediction - test.fantasy_points
            base_error = baseline - test.fantasy_points
            total = (
                history.loc[history.season == season].shape[0]
                if self.horizon == "weekly"
                else history.loc[history.season == season, "player_id"].nunique()
            )
            records.append(
                {
                    "season": int(season),
                    "horizon": self.horizon,
                    "rows": len(test),
                    "coverage": len(test) / total,
                    "model_mae": float(np.abs(error).mean()),
                    "baseline_mae": float(np.abs(base_error).mean()),
                    "model_rmse": float(np.sqrt(np.mean(error**2))),
                    "mae_improvement": float(
                        np.abs(base_error).mean() - np.abs(error).mean()
                    ),
                }
            )
        if not records:
            raise ValueError("Not enough history for requested chronological holdouts")
        return pd.DataFrame(records)
