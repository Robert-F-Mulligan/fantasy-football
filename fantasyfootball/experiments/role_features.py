"""Completed-game role signals; never infer current injuries from future outcomes."""

import numpy as np
import pandas as pd

from fantasyfootball.forecasting.features import WeeklyFeatures


class RoleFeatures:
    def __init__(self, competition=False):
        self.competition = competition

    def build(self, history, fixtures=None):
        stats = ["offense_pct", "target_share", "rushing_att", "receiving_tgt"]
        required = {"player_id", "period", "team", "pos", *stats}
        if not required.issubset(history):
            raise ValueError(f"Missing role columns: {sorted(required - set(history))}")
        if history.duplicated(["player_id", "period"]).any():
            raise ValueError("Duplicate player-period role rows")
        if history.team.isna().any():
            raise ValueError("Missing historical team")
        source = history[["player_id", "period", "team", "pos", *stats]].copy()
        for stat in stats:
            source[stat] = pd.to_numeric(source[stat], errors="raise")
            if np.isinf(source[stat]).any() or source[stat].lt(0).any():
                raise ValueError("Invalid role values")
        if self.competition:
            # Past observed teammates only. Missing/DNP rows are not injury labels.
            for stat in ["rushing_att", "receiving_tgt"]:
                group = source.groupby(["team", "pos", "period"])[stat]
                total = group.transform(lambda s: s.sum(min_count=1))
                unknown = group.transform(lambda s: s.isna().any())
                name = "position_share_" + stat
                source[name] = (source[stat] / total.replace(0, np.nan)).mask(unknown)
                stats.append(name)
        data, columns = WeeklyFeatures().build(history, fixtures)
        if fixtures is not None:
            # Only identity/time keys from forecasts, never their usage or teammates.
            source = pd.concat(
                [source, data[["player_id", "period"]]], ignore_index=True
            )
        source = source.sort_values(["player_id", "period"])
        groups = source.groupby("player_id")
        added = []
        for stat in stats:
            last, change = "role_last_" + stat, "role_change_" + stat
            source[last] = groups[stat].shift(1)
            previous = groups[stat].transform(
                lambda s: s.shift(2).rolling(3, min_periods=2).mean()
            )
            source[change] = source[last] - previous
            added.extend([last, change])
        return data.merge(
            source[["player_id", "period", *added]],
            on=["player_id", "period"],
            how="left",
            validate="one_to_one",
        ), columns + added
