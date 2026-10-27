"""Future schedule coverage using distinct-player slot matching, not forecasts."""

import pandas as pd


class ScheduleCoverage:
    columns = (
        "add_player_id",
        "drop_player_id",
        "week",
        "slots",
        "before_filled",
        "after_filled",
        "status",
    )

    @staticmethod
    def filled(positions, slots):
        """Maximum bipartite matching: a player can cover only one slot."""
        occupants = {}

        def assign(slot, visited):
            for player, position in positions.items():
                if player in visited or position not in slots[slot]:
                    continue
                visited.add(player)
                if player not in occupants or assign(occupants[player], visited):
                    occupants[player] = slot
                    return True
            return False

        for slot in sorted(slots, key=lambda s: (len(slots[s]), s)):
            assign(slot, set())
        return len(occupants)

    def evaluate(
        self, pairs, roster, available, details, schedule, slots, *, season, week
    ):
        weeks = range(week + 1, min(week + 3, 18) + 1)
        games = schedule.loc[
            (pd.to_numeric(schedule.season) == season) & schedule.game_type.eq("REG")
        ]
        known_teams = set(games.home_team.dropna()) | set(games.away_team.dropna())

        def positions(frame, playing):
            result = {}
            for row in frame.to_dict("records"):
                if row["pos"] not in {"QB", "RB", "WR", "TE"}:
                    continue
                if row.get("is_reserve") not in [True, False] or row.get(
                    "is_taxi"
                ) not in [True, False]:
                    return None
                if row["is_reserve"] or row["is_taxi"]:
                    continue
                if pd.isna(row["player_id"]) or row["player_id"] in result:
                    return None
                info = details.get(str(row["sleeper_id"]), {})
                team = {"LAR": "LA"}.get(info.get("team"), info.get("team"))
                if team not in known_teams:
                    return None
                if team in playing:
                    result[row["player_id"]] = row["pos"]
            return result

        rows = []
        for future in weeks:
            subset = games.loc[pd.to_numeric(games.week) == future]
            teams = list(subset.home_team) + list(subset.away_team)
            valid = (
                bool(teams)
                and len(set(teams)) == len(teams)
                and not pd.isna(teams).any()
            )
            baseline = positions(roster, set(teams)) if valid else None
            before = self.filled(baseline, slots) if baseline is not None else None
            for pair in pairs.to_dict("records"):
                added = available.loc[available.player_id.eq(pair["add_player_id"])]
                dropped = roster.player_id.eq(pair["drop_player_id"])
                proposed = pd.concat([roster.loc[~dropped], added], ignore_index=True)
                candidate = (
                    positions(proposed, set(teams))
                    if valid and len(added) == 1 and dropped.sum() == 1
                    else None
                )
                after = self.filled(candidate, slots) if candidate is not None else None
                rows.append(
                    {
                        "add_player_id": pair["add_player_id"],
                        "drop_player_id": pair["drop_player_id"],
                        "week": future,
                        "slots": len(slots),
                        "before_filled": before,
                        "after_filled": after,
                        "status": "schedule_only"
                        if before is not None and after is not None
                        else "unknown",
                    }
                )
        return pd.DataFrame(rows, columns=self.columns)

    @staticmethod
    def summarize(rows):
        if rows.empty:
            return "No later regular-season weeks in horizon"
        return "; ".join(
            f"W{r.week}: {int(r.before_filled)}/{r.slots} -> {int(r.after_filled)}/{r.slots}"
            if r.status == "schedule_only"
            else f"W{r.week}: unknown coverage"
            for r in rows.itertuples()
        )
