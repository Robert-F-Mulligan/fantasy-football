"""Replaceable projection strategies and walk-forward evaluation."""

from typing import Protocol
import numpy as np
import pandas as pd
from .domain import numeric, players


class ProjectionModel(Protocol):
    def predict(self, history: pd.DataFrame, season: int) -> pd.DataFrame: ...


def validate_history(history):
    data = numeric(players(history), ["season", "games", "fantasy_points"])
    if (data.games <= 0).any() or (data.season % 1 != 0).any():
        raise ValueError("History needs positive games and integer seasons")
    if data.duplicated(["player_id", "season"]).any():
        raise ValueError("History must contain one row per player and season")
    return data


class WeightedHistoryModel:
    """Recency-weighted PPG shrunk toward a positional prior.

    Uses only seasons before the target. Does not predict injuries or rookies.
    """

    def __init__(self, decay=0.6, prior_games=4.0, season_games=17, lookback=3):
        if not 0 < decay <= 1 or not np.isfinite(prior_games) or prior_games < 0:
            raise ValueError(
                "decay must be in (0, 1]; prior_games must be finite and nonnegative"
            )
        if not isinstance(lookback, int) or lookback < 1 or not 0 < season_games <= 17:
            raise ValueError(
                "lookback must be positive; season_games must be in (0, 17]"
            )
        self.decay, self.prior_games = decay, prior_games
        self.season_games, self.lookback = season_games, lookback

    def predict(self, history, season):
        if not isinstance(season, int):
            raise ValueError("Target season must be an integer")
        data = validate_history(history)
        data = data.loc[data.season.between(season - self.lookback, season - 1)].copy()
        if data.empty:
            raise ValueError("No historical seasons precede the target within lookback")
        data["weight"] = self.decay ** (season - 1 - data.season)
        data["weighted_points"] = data.fantasy_points * data.weight
        data["weighted_games"] = data.games * data.weight
        priors = data.groupby("pos")[["weighted_points", "weighted_games"]].sum()
        priors = priors.weighted_points / priors.weighted_games
        totals = data.groupby("player_id")[["weighted_points", "weighted_games"]].sum()
        latest = (
            data.sort_values("season")
            .drop_duplicates("player_id", keep="last")
            .set_index("player_id")
        )
        ppg = (totals.weighted_points + latest.pos.map(priors) * self.prior_games) / (
            totals.weighted_games + self.prior_games
        )
        result = latest[["player_name", "pos"]].copy()
        if "team" in latest:
            result["team"] = latest.team
        games = (
            latest["expected_games"]
            if "expected_games" in latest
            else pd.Series(self.season_games, index=latest.index)
        )
        games = pd.to_numeric(games, errors="raise")
        if not np.isfinite(games).all() or not games.between(0, 17).all():
            raise ValueError("expected_games must be finite and between 0 and 17")
        result["projected_points"] = ppg * games
        result["season"] = season
        result["history_seasons"] = data.groupby("player_id").size()
        return result.reset_index()


class WalkForwardEvaluator:
    def __init__(self, model: ProjectionModel):
        self.model = model

    def evaluate(self, history):
        data = validate_history(history)
        rows = []
        for season in sorted(data.season.unique())[1:]:
            predictions = self.model.predict(
                data.loc[data.season < season].copy(), int(season)
            )
            actual = data.loc[data.season == season, ["player_id", "fantasy_points"]]
            matched = actual.merge(
                predictions[["player_id", "projected_points"]],
                on="player_id",
                validate="one_to_one",
            )
            if matched.empty:
                continue
            error = matched.projected_points - matched.fantasy_points
            rows.append(
                {
                    "season": int(season),
                    "players": len(matched),
                    "coverage": len(matched) / len(actual),
                    "mae": float(error.abs().mean()),
                    "rmse": float(np.sqrt((error**2).mean())),
                }
            )
        if not rows:
            raise ValueError("Evaluation needs two seasons with overlapping players")
        return pd.DataFrame(rows)
