"""Receiver usage with explicit team denominators and missing-data semantics."""

import pandas as pd

from fantasyfootball.core.domain import numeric


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
        missing = required - set(plays)
        if missing:
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
        if (
            not isinstance(through_week, int)
            or isinstance(through_week, bool)
            or not 1 <= through_week <= 18
        ):
            raise ValueError("through_week must be an integer from 1 to 18")
        data = numeric(plays, ["season", "week"])
        if (
            data[["game_id", "play_id"]].isna().any().any()
            or data.duplicated(["game_id", "play_id"]).any()
        ):
            raise ValueError("Unique game_id/play_id keys are required")
        data = data.loc[
            data.season.eq(season)
            & data.week.le(through_week)
            & data.season_type.eq("REG")
            & data.play_type.eq("pass")
        ].copy()
        if not data.two_point_attempt.isin([0, 1]).all():
            raise ValueError(
                "Eligible pass plays require explicit two_point_attempt 0/1 flags"
            )
        data = data.loc[data.two_point_attempt.eq(0)].copy()
        # nflverse represents nullified plays as no_play, not pass.
        identified = data.receiver_player_id.notna() & data.receiver_player_id.astype(
            str
        ).str.strip().ne("")
        omitted = int((~identified).sum())
        data = data.loc[identified].copy()
        if (
            data.posteam.isna().any()
            or data.posteam.astype(str).str.strip().eq("").any()
        ):
            raise ValueError("Identified targets require posteam")
        data["posteam"] = data.posteam.replace({"LAR": "LA", "JAC": "JAX"})
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
