"""Descriptive offense/defense comparisons from one play-by-play snapshot."""

import pandas as pd

from fantasyfootball.core.domain import numeric
from fantasyfootball.research.inputs import (
    ResearchWindow,
    normalize_teams,
    require_binary_flags,
)


class TeamMatchups:
    """Comparable per-play metrics, with observed denominators and no forecast blend."""

    METRICS = ("Dropback EPA", "Rush EPA", "Sack rate")

    def summarize(self, plays, *, season, through_week):
        required = {
            "game_id",
            "play_id",
            "season",
            "week",
            "season_type",
            "posteam",
            "defteam",
            "play_type",
            "two_point_attempt",
            "qb_dropback",
            "rush_attempt",
            "qb_kneel",
            "qb_spike",
            "epa",
            "sack",
        }
        data = ResearchWindow(season, through_week).select(
            plays, required=required, play_types=("pass", "run")
        )
        flags = [
            "two_point_attempt",
            "qb_dropback",
            "rush_attempt",
            "qb_kneel",
            "qb_spike",
        ]
        require_binary_flags(data, flags)
        data = data.loc[
            data.two_point_attempt.eq(0) & data.qb_kneel.eq(0) & data.qb_spike.eq(0)
        ].copy()
        data = normalize_teams(data, ["posteam", "defteam"])
        for column in ["epa", "sack"]:
            data[column] = pd.to_numeric(data[column], errors="raise")
            numeric(data.loc[data[column].notna()], [column])
        if not data.sack.dropna().isin([0, 1]).all():
            raise ValueError("sack must be zero, one or missing")
        rows = []
        specs = [
            ("Dropback EPA", data.qb_dropback.eq(1), "epa", "points/play"),
            (
                "Rush EPA",
                data.rush_attempt.eq(1) & data.qb_dropback.eq(0),
                "epa",
                "points/play",
            ),
            ("Sack rate", data.qb_dropback.eq(1), "sack", "fraction"),
        ]
        for unit, team_column in [("Offense", "posteam"), ("Defense", "defteam")]:
            for metric, mask, field, units in specs:
                for team, group in data.loc[mask].groupby(team_column, sort=True):
                    observed = group[field].dropna()
                    rows.append(
                        {
                            "team": team,
                            "unit": unit,
                            "metric": metric,
                            "value": observed.mean(),
                            "observations": len(observed),
                            "eligible_plays": len(group),
                            "games": group.game_id.nunique(),
                            "units": units,
                            "season": season,
                            "through_week": through_week,
                        }
                    )
        return pd.DataFrame(
            rows,
            columns=[
                "team",
                "unit",
                "metric",
                "value",
                "observations",
                "eligible_plays",
                "games",
                "units",
                "season",
                "through_week",
            ],
        )

    def compare(self, summary, *, offense, defense):
        aliases = {"LAR": "LA", "JAC": "JAX"}
        offense, defense = aliases.get(offense, offense), aliases.get(defense, defense)
        if offense == defense:
            raise ValueError("Choose different offense and defense teams")
        if summary[["season", "through_week"]].drop_duplicates().shape[0] != 1:
            raise ValueError("Comparison requires one season and cutoff")
        if summary.duplicated(["team", "unit", "metric"]).any():
            raise ValueError("Duplicate team/unit/metric rows")
        result = summary.loc[
            (summary.team.eq(offense) & summary.unit.eq("Offense"))
            | (summary.team.eq(defense) & summary.unit.eq("Defense"))
        ].copy()
        if set(result.unit) != {"Offense", "Defense"}:
            raise ValueError("Both requested teams need observations")
        return result.reset_index(drop=True)
