"""Explicit one-week add/drop scenarios, never transaction recommendations."""

import pandas as pd

from fantasyfootball.lineups.weekly import WeeklyLineupPlanner


class AddDropEvaluator:
    columns = (
        "add_player_id",
        "add_player_name",
        "add_pos",
        "drop_player_id",
        "drop_player_name",
        "drop_pos",
        "baseline_points",
        "after_points",
        "net_gain",
    )

    def evaluate(self, roster, projections, available, candidates, slots):
        """Only consider eligible, unassigned RB/WR/TE bench players for removal.

        All scenarios optimize the complete remaining offensive roster, retaining
        exact locked slots. Signed gains expose lost production as well as gains.
        """
        roster = roster.copy()
        available = available.copy()
        roster["locked_slot"] = roster.locked_slot.fillna("")
        available["locked_slot"] = available.locked_slot.fillna("")
        planner = WeeklyLineupPlanner()
        baseline = float(
            planner.recommend(projections, roster, slots).projected_points.sum()
        )
        for flag in ["is_reserve", "is_taxi"]:
            if flag not in roster or not roster[flag].isin([True, False]).all():
                raise ValueError(
                    "Explicit reserve and taxi flags required for drop comparisons"
                )
        bench = roster.loc[
            roster.availability.eq("eligible")
            & roster.pos.isin(["RB", "WR", "TE"])
            & roster.starter_slot.fillna("").eq("")
            & roster.locked_slot.fillna("").eq("")
            & ~roster.is_reserve
            & ~roster.is_taxi
        ]
        if candidates.player_id.isna().any() or candidates.player_id.duplicated().any():
            raise ValueError("Add candidates require unique canonical IDs")
        if set(candidates.player_id) & set(roster.player_id.dropna()):
            raise ValueError("Add candidate is already on the roster")
        rows = []
        for candidate in candidates.to_dict("records"):
            context = available.loc[available.player_id.eq(candidate["player_id"])]
            if len(context) != 1 or context.iloc[0].availability != "eligible":
                continue
            if context.iloc[0].pos not in {"RB", "WR", "TE"}:
                continue
            for drop in bench.to_dict("records"):
                proposed = pd.concat(
                    [roster.loc[roster.player_id.ne(drop["player_id"])], context],
                    ignore_index=True,
                )
                points = pd.concat(
                    [
                        projections.loc[projections.player_id.ne(drop["player_id"])],
                        pd.DataFrame([candidate]),
                    ],
                    ignore_index=True,
                )
                try:
                    after = float(
                        planner.recommend(
                            points, proposed, slots
                        ).projected_points.sum()
                    )
                except ValueError:
                    continue  # Do not display scenarios that cannot fill the lineup.
                rows.append(
                    {
                        "add_player_id": candidate["player_id"],
                        "add_player_name": candidate["player_name"],
                        "add_pos": candidate["pos"],
                        "drop_player_id": drop["player_id"],
                        "drop_player_name": drop["player_name"],
                        "drop_pos": drop["pos"],
                        "baseline_points": baseline,
                        "after_points": after,
                        "net_gain": after - baseline,
                    }
                )
        result = pd.DataFrame(rows, columns=self.columns)
        return result.sort_values(
            [
                "net_gain",
                "add_player_name",
                "drop_player_name",
                "add_player_id",
                "drop_player_id",
            ],
            ascending=[False, True, True, True, True],
            kind="stable",
        ).reset_index(drop=True)
