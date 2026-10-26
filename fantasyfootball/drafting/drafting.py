"""Draft valuation, tiering and conditional ADP availability strategies."""

from math import erfc, sqrt
from typing import Protocol
import numpy as np
import pandas as pd
from fantasyfootball.core.domain import LeagueSettings, numeric, players


class ReplacementStrategy(Protocol):
    def baselines(self, projections: pd.DataFrame, league: LeagueSettings) -> dict: ...


class StarterReplacement:
    """First player outside league-wide starting demand, including flex slots."""

    def baselines(self, projections, league):
        demand = {pos: league.teams * count for pos, count in league.starters.items()}
        remaining = []
        for pos, group in projections.groupby("pos", sort=True):
            ranked = group.sort_values(
                ["projected_points", "player_id"], ascending=[False, True]
            )
            if pos in league.flex_positions:
                remaining.append(ranked.iloc[demand.get(pos, 0) :])
        if remaining and league.flex:
            pool = pd.concat(remaining).sort_values(
                ["projected_points", "player_id"], ascending=[False, True]
            )
            for pos, count in (
                pool.head(league.teams * league.flex).pos.value_counts().items()
            ):
                demand[pos] = demand.get(pos, 0) + int(count)
        baselines = {}
        for pos, group in projections.groupby("pos"):
            ranked = group.projected_points.sort_values(ascending=False)
            count = demand.get(pos, 0)
            if count >= len(ranked):
                raise ValueError(
                    f"Insufficient {pos} depth: need more than {count} players to estimate replacement"
                )
            baselines[pos] = float(ranked.iloc[count])
        return baselines


class GapTiers:
    """Start a new tier after an adjacent projected-points drop exceeds gap."""

    def __init__(self, gap=25.0):
        if not np.isfinite(gap) or gap <= 0:
            raise ValueError("Tier gap must be positive and finite")
        self.gap = gap

    def assign(self, board):
        result = pd.Series(index=board.index, dtype="int64")
        for _, group in board.groupby("pos"):
            ranked = group.sort_values(
                ["projected_points", "player_id"], ascending=[False, True]
            )
            result.loc[ranked.index] = (
                ranked.projected_points.diff().abs().gt(self.gap).cumsum() + 1
            ).to_numpy()
        return result.astype(int)


class ADPAvailability:
    """Normal ADP heuristic conditional on a player still being on the board.

    Probabilities are assumptions, not calibrated forecasts. Missing ADP or
    dispersion stays unknown. Supply adp_std from observed drafts when possible.
    """

    def probability(self, adp, std, pick, current_pick=1):
        if (
            not isinstance(pick, int)
            or not isinstance(current_pick, int)
            or current_pick < 1
            or pick < current_pick
        ):
            raise ValueError("Picks must be integers with 1 <= current_pick <= pick")
        if pd.isna(adp) or pd.isna(std):
            return np.nan
        if not np.isfinite(adp) or not np.isfinite(std) or adp <= 0 or std <= 0:
            raise ValueError("ADP and adp_std must be positive and finite")
        if pick == current_pick:
            return 1.0
        survival = lambda at: 0.5 * erfc((at - 0.5 - adp) / (std * sqrt(2)))
        denominator = survival(current_pick)
        return (
            float(np.clip(survival(pick) / denominator, 0, 1)) if denominator else 0.0
        )


class DraftService:
    def __init__(self, league=None, replacement=None, tiers=None, availability=None):
        self.league = league or LeagueSettings()
        self.replacement = replacement or StarterReplacement()
        self.tiers = tiers or GapTiers()
        self.availability = availability or ADPAvailability()

    def rank(self, projections, *, drafted=(), pick=1, next_pick=None):
        board = numeric(players(projections), ["projected_points"]).reset_index(
            drop=True
        )
        if board.empty or board.player_id.duplicated().any():
            raise ValueError(
                "Projections must be nonempty with unique player_id values"
            )
        eligible = {p for p, n in self.league.starters.items() if n} | (
            set(self.league.flex_positions) if self.league.flex else set()
        )
        if not set(board.pos).issubset(eligible):
            raise ValueError(
                f"Unsupported positions: {sorted(set(board.pos) - eligible)}"
            )
        missing = {p for p, n in self.league.starters.items() if n} - set(board.pos)
        if missing:
            raise ValueError(f"Missing starting positions: {sorted(missing)}")
        baselines = self.replacement.baselines(board, self.league)
        board["replacement_points"] = board.pos.map(baselines)
        board["value_over_replacement"] = (
            board.projected_points - board.replacement_points
        )
        board["tier"] = self.tiers.assign(board)
        board = board.sort_values(
            ["value_over_replacement", "projected_points", "player_id"],
            ascending=[False, False, True],
        )
        board["value_rank"] = np.arange(1, len(board) + 1)
        for col in ("adp", "adp_std"):
            if col not in board:
                board[col] = np.nan
            board[col] = pd.to_numeric(board[col], errors="raise")
            known = board[col].dropna()
            if not np.isfinite(known).all() or (known <= 0).any():
                raise ValueError(f"{col} must be positive and finite when known")
        board["adp_value_gap"] = board.adp - board.value_rank
        target_pick = pick if next_pick is None else next_pick
        self.availability.probability(np.nan, np.nan, target_pick, pick)
        board["available_next_pick"] = [
            self.availability.probability(a, s, target_pick, pick)
            for a, s in zip(board.adp, board.adp_std)
        ]
        return board.loc[~board.player_id.isin({str(p) for p in drafted})].reset_index(
            drop=True
        )


def next_snake_pick(pick, teams):
    if not isinstance(pick, int) or not isinstance(teams, int) or pick < 1 or teams < 1:
        raise ValueError("pick and teams must be positive integers")
    round_index, offset = divmod(pick - 1, teams)
    return (round_index + 1) * teams + (teams - offset)
