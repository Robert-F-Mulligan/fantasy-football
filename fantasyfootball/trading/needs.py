"""Recommendation constraints that preserve positional strength and usable depth."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RosterNeedsPolicy:
    priority_positions: tuple = ()

    def __post_init__(self):
        if not set(self.priority_positions).issubset({"QB", "RB", "WR", "TE"}):
            raise ValueError("Unknown trade priority position")

    def assess(self, calculator, mine, after, result):
        reasons = []
        impact = []
        priority_gain = 0.0
        if result["status"] != "estimated":
            return {
                "eligible": False,
                "reasons": ["Incomplete forecast coverage"],
                "priority_gain": None,
                "position_impact": [],
            }
        weekly = result["weekly"]
        if round(result["my_gain"], 1) <= 0 or round(result["partner_gain"], 1) <= 0:
            reasons.append("Does not improve both teams projected starting lineups")
        if any(
            row["my_after"]["filled"] < row["my_before"]["filled"]
            or row["partner_after"]["filled"] < row["partner_before"]["filled"]
            for row in weekly
        ):
            reasons.append("Creates a new weekly starting-lineup vacancy")
        if sum(row["my_gain"] > 0.05 for row in weekly) == 1 and not any(
            row["my_gain"] > 0.05
            and row["my_before"]["filled"] == row["my_before"]["slots"]
            for row in weekly
        ):
            reasons.append(
                "Gain is only temporary vacancy coverage; use waivers for a bye-week patch"
            )
        if self.priority_positions and not any(
            calculator.players.loc[pid, "pos"] in self.priority_positions
            for pid in result["receive"]
        ):
            reasons.append("Does not acquire a player at a priority position")
        for pos in self.priority_positions:
            before_ids = [
                pid for pid in mine if calculator.players.loc[pid, "pos"] == pos
            ]
            after_ids = [
                pid for pid in after if calculator.players.loc[pid, "pos"] == pos
            ]
            if len(after_ids) < len(before_ids):
                reasons.append(f"Reduces {pos} roster depth")
            needed = max(
                1, sum(set(eligible) == {pos} for eligible in calculator.slots.values())
            )
            for week in calculator.weeks:
                before = self.profile(calculator, before_ids, week, needed)
                changed = self.profile(calculator, after_ids, week, needed)
                if before is None or changed is None:
                    reasons.append(f"Unknown {pos} depth in week {week}")
                    continue
                impact.append(
                    {"position": pos, "week": week, "before": before, "after": changed}
                )
                priority_gain += changed["starter_points"] - before["starter_points"]
                if changed["available"] < min(before["available"], needed + 1):
                    reasons.append(
                        f"Reduces {pos} starter/backup coverage in week {week}"
                    )
                if changed["starter_points"] < before["starter_points"] - 1e-8:
                    reasons.append(f"Weakens projected {pos} starters in week {week}")
                if changed["depth_points"] < before["depth_points"] - 1e-8:
                    reasons.append(
                        f"Weakens projected {pos} injury cover in week {week}"
                    )
        if self.priority_positions and round(priority_gain, 1) <= 0:
            reasons.append("Does not improve priority-position starting points")
        return {
            "eligible": not reasons,
            "reasons": list(dict.fromkeys(reasons)),
            "priority_gain": priority_gain,
            "position_impact": impact,
        }

    @staticmethod
    def profile(calculator, ids, week, needed):
        points = []
        for pid in ids:
            if (pid, week) not in calculator.projections.index:
                return None
            row = calculator.projections.loc[(pid, week)]
            if row.status == "unknown":
                return None
            if row.status == "projected":
                points.append(float(row.projected_points))
        points.sort(reverse=True)
        return {
            "available": len(points),
            "starter_points": sum(points[:needed]),
            "depth_points": sum(points[: needed + 1]),
            "required_starters": needed,
        }
