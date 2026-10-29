"""Neutral-situation play calling with explicit observed context coverage."""

import pandas as pd

from fantasyfootball.core.domain import numeric
from fantasyfootball.research.inputs import (
    ResearchWindow,
    normalize_teams,
    require_binary_flags,
)


class NeutralTendencies:
    """First/second downs, >120 seconds in the half, offense WP in [0.2, 0.8]."""

    def summarize(self, plays, *, season, through_week):
        required = {
            "game_id",
            "play_id",
            "season",
            "week",
            "season_type",
            "posteam",
            "play_type",
            "two_point_attempt",
            "qb_kneel",
            "qb_spike",
            "qb_dropback",
            "rush_attempt",
            "down",
            "half_seconds_remaining",
            "wp",
        }
        data = ResearchWindow(season, through_week).select(
            plays, required=required, play_types=("pass", "run")
        )
        require_binary_flags(
            data,
            [
                "two_point_attempt",
                "qb_kneel",
                "qb_spike",
                "qb_dropback",
                "rush_attempt",
            ],
        )
        data = data.loc[
            data.two_point_attempt.eq(0) & data.qb_kneel.eq(0) & data.qb_spike.eq(0)
        ].copy()
        data = normalize_teams(data, ["posteam"])
        for column in ["down", "half_seconds_remaining", "wp"]:
            data[column] = pd.to_numeric(data[column], errors="raise")
            numeric(data.loc[data[column].notna()], [column])
        if not data.wp.dropna().between(0, 1).all():
            raise ValueError("wp must be between zero and one")
        if (
            not data.down.dropna().isin([1, 2, 3, 4]).all()
            or data.half_seconds_remaining.dropna().lt(0).any()
        ):
            raise ValueError("Invalid down or half clock")
        if (~(data.qb_dropback.eq(1) | data.rush_attempt.eq(1))).any():
            raise ValueError("Eligible plays require a dropback or rush classification")
        known = data[["down", "half_seconds_remaining", "wp"]].notna().all(axis=1)
        data["context_known"] = known
        data["neutral"] = (
            known
            & data.down.isin([1, 2])
            & data.half_seconds_remaining.gt(120)
            & data.wp.between(0.2, 0.8)
        )
        rows = []
        for team, group in data.groupby("posteam", sort=True):
            neutral = group.loc[group.neutral]
            dropbacks = int(neutral.qb_dropback.sum())
            rows.append(
                {
                    "team": team,
                    "dropbacks": dropbacks,
                    "designed_rushes": len(neutral) - dropbacks,
                    "neutral_plays": len(neutral),
                    "dropback_rate": dropbacks / len(neutral)
                    if len(neutral)
                    else float("nan"),
                    "eligible_plays": len(group),
                    "incomplete_context": int((~group.context_known).sum()),
                    "neutral_games": neutral.game_id.nunique(),
                    "season": season,
                    "through_week": through_week,
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "team",
                "dropbacks",
                "designed_rushes",
                "neutral_plays",
                "dropback_rate",
                "eligible_plays",
                "incomplete_context",
                "neutral_games",
                "season",
                "through_week",
            ],
        )
