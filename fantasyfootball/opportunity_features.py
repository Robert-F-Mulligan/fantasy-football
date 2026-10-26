"""Experimental snap and scoring-opportunity inputs, never enabled implicitly."""

import numpy as np
import pandas as pd

from .features import WeeklyFeatures

KEYS = ["player_id", "season", "week", "team"]
TEAM_KEYS = ["season", "week", "team"]
PBP_COLUMNS = [
    "season",
    "week",
    "season_type",
    "game_id",
    "play_id",
    "posteam",
    "play_type",
    "rush_attempt",
    "pass_attempt",
    "qb_kneel",
    "qb_spike",
    "two_point_attempt",
    "rusher_player_id",
    "receiver_player_id",
    "yardline_100",
    "air_yards",
]


def normalize_teams(frame):
    frame = frame.copy()
    frame["team"] = frame.team.replace(
        {"LAR": "LA", "JAC": "JAX", "OAK": "LV", "SD": "LAC"}
    )
    return frame


def attach_opportunities(weekly, snaps, aliases, pbp):
    """Join provider IDs, retain missing coverage, and count valid recorded plays."""
    weekly = normalize_teams(weekly)
    snaps = normalize_teams(snaps.loc[snaps.game_type.eq("REG")])
    mapping = aliases.loc[aliases.provider.eq("pfr"), ["external_id", "player_id"]]
    if mapping.external_id.duplicated().any():
        raise ValueError("Ambiguous PFR aliases")
    snaps = snaps.merge(
        mapping,
        left_on="pfr_player_id",
        right_on="external_id",
        how="left",
        validate="many_to_one",
    )
    mapped = snaps.loc[snaps.player_id.notna(), KEYS + ["offense_pct"]]
    result = weekly.merge(mapped, on=KEYS, how="left", validate="one_to_one")
    if not result.offense_pct.dropna().between(0, 1).all():
        raise ValueError("Snap share outside [0, 1]")
    pbp = normalize_teams(pbp.rename(columns={"posteam": "team"}))
    pbp = pbp.loc[pbp.season_type.eq("REG")].copy()
    if pbp.duplicated(["game_id", "play_id"]).any():
        raise ValueError("Duplicate play IDs")
    coverage = pbp.dropna(subset=["team"]).groupby(TEAM_KEYS).game_id.nunique()
    if coverage.gt(1).any():
        raise ValueError("Multiple games in a team-week")
    valid = pbp.loc[pbp.play_type.ne("no_play") & pbp.two_point_attempt.eq(0)]
    specs = [
        (
            "goal_line_carries",
            "rusher_player_id",
            valid.rush_attempt.eq(1) & valid.qb_kneel.eq(0),
            ["yardline_100"],
        ),
        (
            "end_zone_targets",
            "receiver_player_id",
            valid.pass_attempt.eq(1) & valid.qb_spike.eq(0),
            ["yardline_100", "air_yards"],
        ),
    ]
    for name, identity, mask, required in specs:
        plays = valid.loc[mask & valid[identity].notna()].copy()
        known = plays[required].notna().all(axis=1)
        qualifies = (
            plays.yardline_100.le(5)
            if name == "goal_line_carries"
            else plays.air_yards.ge(plays.yardline_100)
        )
        plays[name] = (known & qualifies).astype(float)
        plays["unknown"] = ~known
        plays = plays.rename(columns={identity: "player_id"})
        counts = (
            plays.groupby(KEYS)
            .agg(**{name: (name, "sum"), "unknown": ("unknown", "any")})
            .reset_index()
        )
        counts.loc[counts.unknown, name] = np.nan
        counts["recorded"] = True
        result = result.merge(
            counts[KEYS + [name, "recorded"]],
            on=KEYS,
            how="left",
            validate="one_to_one",
        )
        covered = pd.MultiIndex.from_frame(result[TEAM_KEYS]).isin(coverage.index)
        # Zero only for a covered game with no recorded opportunities for this player.
        result.loc[covered & result.recorded.isna(), name] = 0.0
        result = result.drop(columns="recorded")
    audit = {
        "rows": len(result),
        "unmapped_snap_rows": int(snaps.player_id.isna().sum()),
        "coverage_by_season": result.groupby("season")[
            ["offense_pct", "goal_line_carries", "end_zone_targets"]
        ]
        .agg(lambda s: float(s.notna().mean()))
        .to_dict(),
    }
    return result, audit


class OpportunityFeatures:
    def __init__(self, high_value=False):
        self.high_value = high_value

    def build(self, history, fixtures=None):
        stats = ["offense_pct"] + (
            ["goal_line_carries", "end_zone_targets"] if self.high_value else []
        )
        if not set(stats).issubset(history):
            raise ValueError("Missing opportunity columns")
        if history.duplicated(["player_id", "period"]).any():
            raise ValueError("Duplicate player-period opportunities")
        data, columns = WeeklyFeatures().build(history, fixtures)
        source = history[["player_id", "period", *stats]].copy()
        for stat in stats:
            source[stat] = pd.to_numeric(source[stat], errors="raise")
            if np.isinf(source[stat]).any():
                raise ValueError("Infinite opportunity values")
        if fixtures is not None:
            source = pd.concat(
                [source, data[["player_id", "period"]]], ignore_index=True
            )
        source = source.sort_values(["player_id", "period"])
        added = []
        for stat in stats:
            for window in [4, 12]:
                col = f"opportunity_prior{window}_{stat}"
                source[col] = source.groupby("player_id")[stat].transform(
                    lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
                )
                added.append(col)
        return data.merge(
            source[["player_id", "period", *added]],
            on=["player_id", "period"],
            validate="one_to_one",
            how="left",
        ), columns + added
