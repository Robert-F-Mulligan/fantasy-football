"""League rules and explicit input contracts for analysis."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
import numpy as np
import pandas as pd


def numeric(frame, columns):
    result = frame.copy()
    missing = set(columns) - set(result.columns)
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
    for column in columns:
        result[column] = pd.to_numeric(result[column], errors="raise")
        if not np.isfinite(result[column]).all():
            raise ValueError(f"{column} must contain finite numbers")
    return result


def players(frame):
    required = {"player_id", "player_name", "pos"}
    if not required.issubset(frame):
        raise ValueError(f"Player data requires {sorted(required)}")
    result = frame.copy()
    for col in required:
        if result[col].isna().any() or result[col].astype(str).str.strip().eq("").any():
            raise ValueError(f"{col} cannot be blank")
        result[col] = result[col].astype(str).str.strip()
    result["pos"] = result.pos.str.upper()
    return result


@dataclass(frozen=True)
class ScoringRules:
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "passing_yds": 0.04,
            "passing_td": 4,
            "passing_int": -2,
            "rushing_yds": 0.1,
            "rushing_td": 6,
            "receiving_rec": 1,
            "receiving_yds": 0.1,
            "receiving_td": 6,
            "fumbles_lost": -2,
        }
    )

    def __post_init__(self):
        if not self.weights or not all(np.isfinite(v) for v in self.weights.values()):
            raise ValueError("Scoring weights must be nonempty and finite")
        object.__setattr__(self, "weights", MappingProxyType(dict(self.weights)))

    def score(self, stats):
        """Require configured stats; callers must explicitly fill true zeros."""
        data = numeric(stats, self.weights)
        return sum(data[col] * weight for col, weight in self.weights.items())


@dataclass(frozen=True)
class LeagueSettings:
    teams: int = 12
    starters: Mapping[str, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
    )
    flex: int = 1
    flex_positions: tuple[str, ...] = ("RB", "WR", "TE")
    scoring: ScoringRules = field(default_factory=ScoringRules)

    def __post_init__(self):
        counts = [self.teams, self.flex, *self.starters.values()]
        if (
            any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in counts)
            or self.teams < 1
        ):
            raise ValueError(
                "League counts must be nonnegative integers; teams must be positive"
            )
        if not self.starters or not any(self.starters.values()):
            raise ValueError("At least one starting position is required")
        if self.flex and not self.flex_positions:
            raise ValueError("Flex slots require eligible positions")
        if len({k.upper() for k in self.starters}) != len(self.starters):
            raise ValueError("Duplicate position keys after normalization")
        object.__setattr__(
            self,
            "starters",
            MappingProxyType({k.upper(): v for k, v in self.starters.items()}),
        )
        object.__setattr__(
            self, "flex_positions", tuple(p.upper() for p in self.flex_positions)
        )

    @classmethod
    def from_legacy(cls, config):
        stats = {
            k: v
            for k, v in config.items()
            if k.startswith(("passing_", "rushing_", "receiving_", "fumbles"))
        }
        return cls(
            teams=config["team_n"],
            starters={
                p.upper(): config.get(p, 0)
                for p in ("qb", "rb", "wr", "te", "dst", "k")
            },
            flex=config.get("flex", 0),
            scoring=ScoringRules(stats),
        )
