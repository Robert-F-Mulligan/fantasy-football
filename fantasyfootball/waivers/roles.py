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
                "Depth unavailable",
            )
        _team, pos, order = entry
        if self.counts[entry] != 1:
            return (
                "conflict",
                None,
                "Conflicting depth listings",
            )
        note = f"Sleeper depth: {pos}{order}"
        if pos == "QB" and order > 1:
            note += "; backup QB, weak opportunity forecast"

        return "listed", order, note

    def annotate(self, frame):
        result = frame.copy()
        values = [self.describe(row.sleeper_id, row.pos) for row in frame.itertuples()]
        for index, column in enumerate(["role_status", "depth_order", "role_note"]):
            result[column] = [value[index] for value in values]
        return result


def workload_notes(history, season, week):
    """Descriptive last-three-game flags, using only completed prior-season-week rows.

    Five opportunities per game is a display threshold, not statistical evidence
    or an adjustment to points/FAAB. Missing usage never becomes zero.
    """
    required = {"season", "week", "player_id", "pos", "rushing_att", "receiving_tgt"}
    if not required.issubset(history):
        return {}
    recent = history.loc[history.season.eq(season) & history.week.lt(week)]
    notes = {}
    for pid, group in recent.sort_values("week").groupby("player_id"):
        rows = group.tail(3)
        if rows.iloc[-1].pos not in {"RB", "WR", "TE"}:
            continue
        usage = rows[["rushing_att", "receiving_tgt"]]
        if usage.isna().any().any() or (usage < 0).any().any():
            continue
        average = usage.sum(axis=1).mean()
        if average < 5:
            notes[pid] = (
                f"Low volume: {average:.1f} carries + targets/game over {len(rows)} recent games."
            )
    return notes
