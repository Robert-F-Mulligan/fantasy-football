"""Descriptive monitoring of the fixed prospective window; no interim inference."""

import math


class MomentumStudy:
    season = 2026
    first_week = 9
    last_week = 17
    minimum_weeks = 8

    @staticmethod
    def totals(samples):
        count = 0
        baseline = candidate = 0.0
        for sample in samples:
            n = sample["paired_rows"]
            b, c = (
                sample["baseline_absolute_error_sum"],
                sample["candidate_absolute_error_sum"],
            )
            if (
                type(n) is not int
                or n < 1
                or not all(math.isfinite(x) and x >= 0 for x in [b, c])
            ):
                raise ValueError("Invalid paired study totals")
            count += n
            baseline += b
            candidate += c
        return {
            "paired_rows": count,
            "baseline_absolute_error_sum": baseline,
            "candidate_absolute_error_sum": candidate,
            "baseline_mae": baseline / count if count else None,
            "candidate_mae": candidate / count if count else None,
            "mae_delta": (candidate - baseline) / count if count else None,
        }

    def summarize(
        self, reports, *, current_season, current_week, outcome_archive_sha256
    ):
        selected = {}
        for report in reports:
            if (
                report["season"] != self.season
                or not self.first_week <= report["week"] <= self.last_week
            ):
                continue
            week = report["week"]
            if week in selected:
                raise ValueError(
                    "Duplicate week: select earliest capture before summarizing"
                )
            selected[week] = report
        weeks, paired, positions = [], [], {}
        for week in range(self.first_week, self.last_week + 1):
            report = selected.get(week)
            item = {
                "week": week,
                "status": "not_yet_captured"
                if (current_season, current_week) <= (self.season, week)
                else "missing_capture",
            }
            if report:
                shadow = report["shadow"]
                item.update(
                    archive_sha256=report["archive_sha256"],
                    captured_at=report["captured_at"],
                    unresolved_rows=report["unresolved_rows"],
                    pregame_rows=report["pregame_rows"],
                    confirmed_dnp_rows=report["confirmed_dnp_rows"],
                    shadow=shadow,
                )
                item["status"] = shadow["status"]
                if shadow["status"] == "scored":
                    if (
                        shadow.get("candidate") != "workload_momentum_v1"
                        or shadow.get("protocol_window") is not True
                    ):
                        raise ValueError("Unexpected candidate or protocol window")
                    paired.append(shadow)
                    for pos, sample in shadow.get("by_position", {}).items():
                        positions.setdefault(pos, []).append(sample)
            weeks.append(item)
        closed = (current_season, current_week) > (self.season, self.last_week)
        status = (
            "collecting"
            if not closed
            else (
                "ready_for_final_analysis"
                if len(paired) >= self.minimum_weeks
                else "insufficient_paired_weeks"
            )
        )
        return {
            "candidate": "workload_momentum_v1",
            "protocol": "docs/PROSPECTIVE_MOMENTUM.md",
            "season": self.season,
            "window": [self.first_week, self.last_week],
            "minimum_paired_weeks": self.minimum_weeks,
            "status": status,
            "paired_weeks": len(paired),
            "weeks": weeks,
            "descriptive_totals": self.totals(paired),
            "by_position": {p: self.totals(v) for p, v in positions.items()},
            "outcome_archive_sha256": outcome_archive_sha256,
            "inference": "Deferred: no interim significance test or promotion. Final analysis requires preregistered block bootstrap and coverage review; readiness is not evidence of improvement.",
            "selection": "Earliest retained capture per league/roster/week; missing candidate never replaced with a later capture.",
        }
