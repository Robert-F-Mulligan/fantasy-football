"""Provider-listed depth context; never a verified starting lineup or workload forecast."""

import math
from collections import Counter


class SleeperRoleContext:
    def __init__(self, details):
        self.details = details
        self.entries = {str(sid): self._entry(info) for sid, info in details.items()}
        self.counts = Counter(
            entry for entry in self.entries.values() if entry is not None
        )

    @staticmethod
    def _entry(info):
        position = info.get("position")
        team = info.get("team")
        order = info.get("depth_chart_order")
        if (
            position not in {"QB", "RB", "WR", "TE"}
            or info.get("depth_chart_position") != position
            or str(info.get("status", "")).casefold() != "active"
            or not isinstance(team, str)
            or not team.strip()
            or isinstance(order, bool)
            or not isinstance(order, (int, float))
            or not math.isfinite(order)
            or order < 1
            or order != int(order)
        ):
            return None
        return ({"LAR": "LA"}.get(team, team), position, int(order))

    def describe(self, sleeper_id, position):
        entry = self.entries.get(str(sleeper_id))
        if position not in {"QB", "RB", "WR", "TE"}:
            return "not_applicable", None, "Role context not modeled for specialists"
        if entry is None or entry[1] != position:
            return (
                "unknown",
                None,
                "Sleeper depth role unknown or inconsistent; verify current role",
            )
        team, pos, order = entry
        if self.counts[entry] != 1:
            return (
                "conflict",
                None,
                "Sleeper depth role conflicts with another active player; verify current role",
            )
        note = f"Sleeper lists {team} {pos} depth {order}; not confirmed for this game"
        if pos == "QB" and order > 1:
            note += (
                "; backup listing: historical points may overstate current opportunity"
            )
        elif order == 1:
            note += "; first listing does not guarantee snaps or touches"
        return "listed", order, note

    def annotate(self, frame):
        result = frame.copy()
        values = [self.describe(row.sleeper_id, row.pos) for row in frame.itertuples()]
        for index, column in enumerate(["role_status", "depth_order", "role_note"]):
            result[column] = [value[index] for value in values]
        return result
