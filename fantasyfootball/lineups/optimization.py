"""Maximum projected-points assignment to explicit roster slots."""

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from fantasyfootball.core.domain import numeric, players


class LineupOptimizer:
    def optimize(
        self,
        projections,
        slots,
        *,
        excluded=(),
        locked=(),
        fixed_slots=None,
        prefer_late_flex=False,
    ):
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
        fixed_slots = {
            slot: str(player) for slot, player in (fixed_slots or {}).items()
        }
        if not set(fixed_slots).issubset(slots) or len(
            set(fixed_slots.values())
        ) != len(fixed_slots):
            raise ValueError("Fixed slots must be known and assign each player once")
        locked = {str(v) for v in locked} | set(fixed_slots.values())
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
        for slot, player_id in fixed_slots.items():
            row = list(slots).index(slot)
            col = board.index[board.player_id.eq(player_id)][0]
            if not eligible[row, col]:
                raise ValueError("Fixed player is not eligible for assigned slot")
            eligible[row, :] = False
            eligible[:, col] = False
            eligible[row, col] = True
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
        selected = selected.reset_index(drop=True)
        if prefer_late_flex:
            selected = self._assign_late_flex(selected, slots, fixed_slots)
        return selected

    @staticmethod
    def _assign_late_flex(selected, slots, fixed_slots):
        """Reassign selected players only; never trade projected points for timing.

        Prefer later kickoffs in slots accepting more distinct positions. Among
        equally flexible assignments, retain as many original slots as possible.
        Missing kickoff information leaves the original assignment untouched.
        """
        if "kickoff" not in selected:
            return selected
        kickoff = pd.to_datetime(selected.kickoff, utc=True, errors="coerce")
        if kickoff.isna().any():
            return selected
        breadth = np.array([len(set(positions)) - 1 for positions in slots.values()])
        if not breadth.any():
            return selected
        rank = kickoff.rank(method="dense").to_numpy()
        eligible = np.array(
            [
                [position in positions for position in selected.pos]
                for positions in slots.values()
            ]
        )
        for slot, player_id in fixed_slots.items():
            row = list(slots).index(slot)
            col = selected.index[selected.player_id.eq(player_id)][0]
            eligible[row, :] = False
            eligible[:, col] = False
            eligible[row, col] = True
        retained = np.array(
            [[slot == original for original in selected.slot] for slot in slots]
        )
        # One unit of timing priority outweighs all slot-retention tie breaks.
        scores = np.outer(breadth, rank) * (len(slots) + 1) + retained
        rows, cols = linear_sum_assignment(np.where(eligible, -scores, np.inf))
        result = selected.iloc[cols].copy()
        result["slot"] = [list(slots)[row] for row in rows]
        return result.reset_index(drop=True)
