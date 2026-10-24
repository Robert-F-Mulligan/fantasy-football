"""Maximum projected-points assignment to explicit roster slots."""

import numpy as np
from scipy.optimize import linear_sum_assignment
from .domain import numeric, players


class LineupOptimizer:
    def optimize(self, projections, slots, *, excluded=(), locked=()):
        if not isinstance(slots, dict) or any(
            not isinstance(positions, (list, tuple))
            or not positions
            or not all(isinstance(pos, str) and pos for pos in positions)
            for positions in slots.values()
        ):
            raise ValueError(
                "Each roster slot needs a nonempty list of eligible positions"
            )
        board = numeric(players(projections), ["projected_points"])
        if board.player_id.duplicated().any():
            raise ValueError("Player IDs must be unique")
        locked = {str(v) for v in locked}
        excluded = {str(v) for v in excluded}
        if locked & excluded:
            raise ValueError("A player cannot be both locked and excluded")
        board = board[~board.player_id.isin(excluded)].reset_index(drop=True)
        if not locked.issubset(set(board.player_id)):
            raise ValueError("Locked player missing from candidate pool")
        if not slots or len(locked) > len(slots):
            raise ValueError("Invalid roster slots or too many locks")
        if len(board) < len(slots):
            raise ValueError("Insufficient players to fill lineup")
        eligible = np.array(
            [[p in positions for p in board.pos] for positions in slots.values()]
        )
        scores = np.tile(board.projected_points.to_numpy(), (len(slots), 1))
        # Bonus larger than the maximum possible lineup-score difference makes
        # every feasible locked player mandatory. Verify after assignment too.
        bonus = (np.abs(scores).max() + 1) * 2 * len(slots)
        scores = scores + board.player_id.isin(locked).to_numpy() * bonus
        costs = np.where(eligible, -scores, np.inf)
        try:
            rows, cols = linear_sum_assignment(costs)
        except ValueError as exc:
            raise ValueError(
                "Cannot fill all roster slots with eligible players"
            ) from exc
        selected = board.iloc[cols].copy()
        if len(rows) != len(slots) or not locked.issubset(set(selected.player_id)):
            raise ValueError("No feasible lineup satisfies all locks and slots")
        selected.insert(0, "slot", [list(slots)[row] for row in rows])
        return selected.reset_index(drop=True)
