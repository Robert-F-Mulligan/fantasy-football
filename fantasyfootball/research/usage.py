"""Receiver usage with explicit team denominators and missing-data semantics."""

import pandas as pd

from fantasyfootball.core.domain import numeric
from fantasyfootball.research.inputs import (
    ResearchWindow,
    normalize_teams,
    require_binary_flags,
)


class ReceiverUsage:
    """Summarize identified targets from regular-season, non-nullified pass plays.

    Keep team stints separate when players transfer. Air yards are signed; shares
    are unavailable when a team's denominator is incomplete or nonpositive.
    """

    def summarize(self, plays, *, season, through_week):
        required = {
            "game_id",
            "play_id",
            "season",
            "week",
            "season_type",
            "play_type",
            "two_point_attempt",
            "posteam",
            "receiver_player_id",
            "receiver_player_name",
            "air_yards",
        }
        data = ResearchWindow(season, through_week).select(
            plays, required=required, play_types=("pass",)
        )
        require_binary_flags(data, ["two_point_attempt"])
        data = data.loc[data.two_point_attempt.eq(0)].copy()
        # nflverse represents nullified plays as no_play, not pass.
        identified = data.receiver_player_id.notna() & data.receiver_player_id.astype(
            str
        ).str.strip().ne("")
        omitted = int((~identified).sum())
        data = data.loc[identified].copy()
        data = normalize_teams(data, ["posteam"])
        data["receiver_player_id"] = data.receiver_player_id.astype(str)
        data["air_yards"] = pd.to_numeric(data.air_yards, errors="raise")
        numeric(data.loc[data.air_yards.notna()], ["air_yards"])
        data = data.sort_values(["week", "game_id", "play_id"])
        result = (
            data.groupby(["posteam", "receiver_player_id"], sort=True)
            .agg(
                player_name=("receiver_player_name", "last"),
                targets=("play_id", "size"),
                air_yards=(
                    "air_yards",
                    lambda values: values.sum(min_count=len(values)),
                ),
                games=("game_id", "nunique"),
            )
            .reset_index()
            .rename(columns={"posteam": "team", "receiver_player_id": "player_id"})
        )
        result["player_name"] = result.player_name.fillna(result.player_id)
        result["team_targets"] = result.groupby("team").targets.transform("sum")
        totals = data.groupby("posteam").air_yards.agg(
            lambda values: values.sum(min_count=len(values))
        )
        result["team_air_yards"] = result.team.map(totals)
        result["target_share"] = result.targets / result.team_targets
        result["air_yard_share"] = result.air_yards / result.team_air_yards.where(
            result.team_air_yards.gt(0)
        )
        result["season"] = season
        result["through_week"] = through_week
        result = result.sort_values(
            ["team", "targets", "player_id"], ascending=[True, False, True]
        ).reset_index(drop=True)
        return result, {
            "unidentified_pass_plays": omitted,
            "identified_targets": len(data),
            "definition": "Shares of identified receiver targets; unidentified pass plays excluded. Team stints stay separate.",
        }
