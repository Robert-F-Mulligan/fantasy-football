"""Experimental, strictly lagged usage features. Not enabled in production."""

import numpy as np
import pandas as pd

from fantasyfootball.forecasting.features import WeeklyFeatures


class UsageFeatures:
    def __init__(self, trends=False):
        self.trends = trends

    def build(self, history, fixtures=None):
        required = {"team", "target_share", "air_yards_share", "rushing_att"}
        if not required.issubset(history):
            raise ValueError(
                f"Missing usage columns: {sorted(required - set(history))}"
            )
        if history.duplicated(["player_id", "period"]).any():
            raise ValueError("Duplicate player-period usage rows")
        data, columns = WeeklyFeatures().build(history, fixtures)
        usage = history.copy()
        for col in ["target_share", "air_yards_share", "rushing_att"]:
            usage[col] = pd.to_numeric(usage[col], errors="raise")
            if np.isinf(usage[col]).any():
                raise ValueError("Infinite usage values")
        if usage.team.isna().any():
            raise ValueError("Missing historical team for usage shares")
        # Denominator uses only observed offensive players in each past team-week.
        team_carries = usage.groupby(["team", "period"]).rushing_att.transform("sum")
        usage["carry_share"] = usage.rushing_att / team_carries.replace(0, np.nan)
        if fixtures is not None:
            # No current-week team, role or usage values are accepted from fixtures.
            future = data[["player_id", "period"]].copy()
            usage = pd.concat([usage, future], ignore_index=True)
        usage = usage.sort_values(["player_id", "period"]).reset_index(drop=True)
        groups = usage.groupby("player_id", sort=False)
        added = []
        for stat in ["target_share", "air_yards_share", "carry_share"]:
            for window in [4, 12]:
                name = f"usage_prior{window}_{stat}"
                usage[name] = groups[stat].transform(
                    lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
                )
                added.append(name)
            if self.trends:
                last = f"usage_last_{stat}"
                delta = f"usage_change_{stat}"
                usage[last] = groups[stat].shift(1)
                usage[delta] = (
                    usage[f"usage_prior4_{stat}"] - usage[f"usage_prior12_{stat}"]
                )
                added += [last, delta]
        data = data.merge(
            usage[["player_id", "period", *added]],
            on=["player_id", "period"],
            how="left",
            validate="one_to_one",
        )
        if self.trends:
            for stat in ["receiving_tgt", "rushing_att", "passing_att"]:
                name = f"usage_change_{stat}"
                data[name] = data[f"prior4_{stat}"] - data[f"prior12_{stat}"]
                added.append(name)
        return data, columns + added
