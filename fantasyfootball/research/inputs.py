"""Shared play-by-play selection contracts for descriptive research."""

from dataclasses import dataclass
from numbers import Integral

from fantasyfootball.core.domain import numeric


@dataclass(frozen=True)
class ResearchWindow:
    season: int
    through_week: int

    def __post_init__(self):
        if (
            isinstance(self.season, bool)
            or not isinstance(self.season, Integral)
            or self.season < 1
        ):
            raise ValueError("season must be a positive integer")
        if (
            isinstance(self.through_week, bool)
            or not isinstance(self.through_week, Integral)
            or not 1 <= self.through_week <= 18
        ):
            raise ValueError("through_week must be an integer from 1 to 18")

    def select(self, plays, *, required, play_types):
        required = set(required) | {
            "game_id",
            "play_id",
            "season",
            "week",
            "season_type",
            "play_type",
        }
        if missing := required - set(plays):
            raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
        data = numeric(plays, ["season", "week"])
        if (
            data.season.lt(1).any()
            or data.season.mod(1).ne(0).any()
            or data.week.lt(1).any()
            or data.week.mod(1).ne(0).any()
        ):
            raise ValueError("Snapshot season/week must be positive integers")
        if (data.season_type.eq("REG") & data.week.gt(18)).any():
            raise ValueError("Regular-season weeks must be between 1 and 18")
        keys = data[["game_id", "play_id"]]
        if (
            keys.isna().any().any()
            or keys.astype(str)
            .apply(lambda column: column.str.strip().eq(""))
            .any()
            .any()
            or data.duplicated(["game_id", "play_id"]).any()
        ):
            raise ValueError("Unique nonblank game_id/play_id keys are required")
        return data.loc[
            data.season.eq(self.season)
            & data.week.le(self.through_week)
            & data.season_type.eq("REG")
            & data.play_type.isin(play_types)
        ].copy()


def require_binary_flags(data, columns):
    """Validate only rows already selected for the research calculation."""
    for column in columns:
        if not data[column].isin([0, 1]).all():
            raise ValueError(f"Eligible plays require explicit {column} zero/one flags")


def normalize_teams(data, columns):
    result = data.copy()
    for column in columns:
        if (
            result[column].isna().any()
            or result[column].astype(str).str.strip().eq("").any()
        ):
            raise ValueError(f"Eligible plays require {column}")
        result[column] = result[column].replace({"LAR": "LA", "JAC": "JAX"})
    return result
