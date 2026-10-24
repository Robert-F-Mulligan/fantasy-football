"""Leakage-safe feature construction for season and weekly forecasting.

Only identity, position and scheduled opponent may come from the forecast row.
All performance features are shifted or joined strictly before its period.
"""

import numpy as np
import pandas as pd
from .domain import players, numeric, ScoringRules

STATS = [
    "passing_att",
    "passing_yds",
    "passing_td",
    "passing_int",
    "rushing_att",
    "rushing_yds",
    "rushing_td",
    "receiving_tgt",
    "receiving_rec",
    "receiving_yds",
    "receiving_td",
]
POSITIONS = ("QB", "RB", "WR", "TE")


def prepare_weekly(frame, scoring=None):
    data = (
        frame.rename(columns={"year": "season"})
        if "season" not in frame
        else frame.copy()
    )
    data = numeric(players(data), ["season", "week", *STATS])
    if data.duplicated(["player_id", "season", "week"]).any():
        raise ValueError("Duplicate player-season-week rows")
    if (
        (data.season % 1 != 0) | (data.week % 1 != 0) | ~data.week.between(1, 18)
    ).any():
        raise ValueError("Expected integer regular-season weeks 1 through 18")
    if not set(data.pos).issubset(POSITIONS):
        raise ValueError("Models currently support QB, RB, WR and TE")
    data["fantasy_points"] = (scoring or ScoringRules()).score(data)
    data["period"] = data.season.astype(int) * 100 + data.week.astype(int)
    if "opp" not in data:
        raise ValueError("Weekly modeling requires scheduled opponent column opp")
    if data.opp.isna().any():
        raise ValueError("Opponent cannot be missing")
    data["age"] = pd.to_numeric(
        data.get("age", pd.Series(np.nan, index=data.index)), errors="coerce"
    )
    return data.sort_values(["period", "player_id"]).reset_index(drop=True)


def _position_features(data):
    for pos in POSITIONS:
        data["position_" + pos] = data.pos.eq(pos).astype(float)
    return data


class WeeklyFeatures:
    def build(self, history, fixtures=None):
        data = history.copy()
        if fixtures is not None:
            fixtures = players(fixtures)
            fixtures = numeric(fixtures, ["season", "week"])
            if fixtures.empty or fixtures.duplicated("player_id").any():
                raise ValueError("Fixtures need unique player IDs for one future week")
            fixtures["period"] = fixtures.season.astype(
                int
            ) * 100 + fixtures.week.astype(int)
            if (
                (fixtures.season % 1 != 0)
                | (fixtures.week % 1 != 0)
                | ~fixtures.week.between(1, 18)
            ).any():
                raise ValueError(
                    "Fixtures need integer regular-season weeks 1 through 18"
                )
            if not set(fixtures.pos).issubset(POSITIONS):
                raise ValueError("Unsupported fixture position")
            if (
                fixtures.period.nunique() != 1
                or fixtures.period.min() <= data.period.max()
            ):
                raise ValueError(
                    "Fixtures must describe one week strictly after history"
                )
            if "opp" not in fixtures or fixtures.opp.isna().any():
                raise ValueError("Fixtures require scheduled opponents")
            # Ignore any accidental current-week performance columns.
            fixtures = fixtures[
                ["player_id", "player_name", "pos", "season", "week", "period", "opp"]
            ]
            data = pd.concat([data, fixtures], ignore_index=True)
        data = data.sort_values(["player_id", "period"]).reset_index(drop=True)
        cols = []
        groups = data.groupby("player_id", sort=False)
        for stat in ["fantasy_points", *STATS]:
            for window in (4, 12):
                name = f"prior{window}_{stat}"
                data[name] = groups[stat].transform(
                    lambda s: s.shift(1).rolling(window, min_periods=1).mean()
                )
                cols.append(name)
        data["prior_age"] = groups.age.shift(1)
        data["previous_games"] = groups.cumcount().astype(float)
        data["points_trend"] = data.prior4_fantasy_points - data.prior12_fantasy_points
        data["yards_per_target"] = (
            data.prior4_receiving_yds / data.prior4_receiving_tgt.replace(0, np.nan)
        )
        data["yards_per_carry"] = (
            data.prior4_rushing_yds / data.prior4_rushing_att.replace(0, np.nan)
        )
        # Aggregate observed opponent outcomes by period first, so no player in
        # the same game/week can leak into another player's defensive feature.
        defense = (
            history.groupby(["opp", "pos", "period"])
            .fantasy_points.mean()
            .reset_index()
        )
        lookup = {
            key: group.sort_values("period")
            for key, group in defense.groupby(["opp", "pos"])
        }
        allowed = []
        for row in data.itertuples():
            prior = lookup.get((row.opp, row.pos))
            if prior is None:
                allowed.append(np.nan)
            else:
                end = np.searchsorted(prior.period.to_numpy(), row.period, side="left")
                allowed.append(prior.fantasy_points.iloc[max(0, end - 8) : end].mean())
        data["opponent_prior_points"] = allowed
        cols += [
            "prior_age",
            "previous_games",
            "points_trend",
            "yards_per_target",
            "yards_per_carry",
            "opponent_prior_points",
        ]
        data = _position_features(data)
        cols += ["position_" + p for p in POSITIONS]
        if fixtures is not None:
            data = data[data.period == fixtures.period.iloc[0]].copy()
        return data, cols


class SeasonFeatures:
    def build(self, weekly, season=None):
        agg = {s: "sum" for s in ["fantasy_points", *STATS]}
        agg.update(
            {"player_name": "last", "pos": "last", "age": "last", "week": "count"}
        )
        annual = (
            weekly.sort_values("period")
            .groupby(["player_id", "season"], as_index=False)
            .agg(agg)
            .rename(columns={"week": "games"})
        )
        if season is not None:
            if season <= annual.season.max():
                raise ValueError("Forecast season must follow history")
            latest = annual[annual.season == season - 1][
                ["player_id", "player_name", "pos"]
            ].copy()
            if latest.empty:
                raise ValueError("No players in the immediately preceding season")
            latest["season"] = season
            annual = pd.concat([annual, latest], ignore_index=True)
        annual = annual.sort_values(["player_id", "season"]).reset_index(drop=True)
        groups = annual.groupby("player_id", sort=False)
        cols = []
        for stat in ["fantasy_points", "games", "age", *STATS]:
            name = "previous_" + stat
            annual[name] = groups[stat].shift(1)
            cols.append(name)
        annual["points_trend"] = groups.fantasy_points.shift(
            1
        ) - groups.fantasy_points.shift(2)
        annual["prior_ppg"] = annual.previous_fantasy_points / annual.previous_games
        annual["yards_per_target"] = (
            annual.previous_receiving_yds
            / annual.previous_receiving_tgt.replace(0, np.nan)
        )
        annual["yards_per_carry"] = (
            annual.previous_rushing_yds / annual.previous_rushing_att.replace(0, np.nan)
        )
        cols += ["points_trend", "prior_ppg", "yards_per_target", "yards_per_carry"]
        prior_season = groups.season.shift(1)
        annual["pos"] = groups.pos.shift(1)
        annual = annual.loc[annual.season - prior_season == 1].copy()
        annual = _position_features(annual)
        cols += ["position_" + p for p in POSITIONS]
        if season is not None:
            annual = annual.loc[annual.season == season].copy()
        return annual, cols
