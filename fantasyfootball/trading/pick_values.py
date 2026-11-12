"""Refresh draft-capital scenarios without confusing rank indices with fantasy points."""

import math


def reprice_picks(inventory, rosters, *, order_rule="unknown"):
    if order_rule not in {"unknown", "random", "reverse_standings"}:
        raise ValueError("Unsupported draft order rule")
    if not inventory.get("picks"):
        return inventory
    count = len(rosters)
    standings = []
    for roster in rosters:
        stats = roster.get("settings", {})
        required = ["wins", "losses", "ties", "fpts"]
        if any(k not in stats for k in required):
            standings = []
            break
        wins, losses, ties = (float(stats[k]) for k in required[:3])
        games = wins + losses + ties
        if games <= 0:
            standings = []
            break
        points = float(stats["fpts"]) + float(stats.get("fpts_decimal", 0)) / 100
        if not all(math.isfinite(x) and x >= 0 for x in [wins, losses, ties, points]):
            raise ValueError("Invalid standings used for pick valuation")
        standings.append(
            (int(roster["roster_id"]), (wins + 0.5 * ties) / games, points)
        )
    ordered = sorted(standings, key=lambda row: (row[1], row[2]))
    slots = {}
    for owner, pct, points in ordered:
        slots[owner] = [
            i + 1 for i, row in enumerate(ordered) if row[1:] == (pct, points)
        ]
    inventory["draft_order_rule"] = order_rule
    inventory["order_status"] = (
        "projected from current reverse standings; final order unassigned"
        if order_rule == "reverse_standings" and standings
        else "unassigned; full round range, not a probability interval"
    )
    inventory["standings_snapshot"] = [
        {"roster_id": owner, "win_fraction": pct, "points_for": points}
        for owner, pct, points in ordered
    ]
    inventory["valuation_method"] = (
        "100 / sqrt(overall pick); heuristic rank index, not an empirical trade-price model"
    )
    inventory["valuation_status"] = (
        "scenario index; keeper costs and future player values excluded"
    )
    for pick in inventory["picks"]:
        rnd = pick["round"]

        def overall(slot, round_number=rnd):
            within = (
                count + 1 - slot
                if inventory["draft_type"] == "snake" and round_number % 2 == 0
                else slot
            )
            return (round_number - 1) * count + within

        def summarize(selected, round_number=rnd):
            positions = sorted(overall(slot) for slot in selected)
            within = [p - (round_number - 1) * count for p in positions]
            selection = f"{round_number}.{min(within):02d}"
            if min(within) != max(within):
                selection += f"-{round_number}.{max(within):02d}"
            return {
                "estimated_overall": sum(positions) / len(positions),
                "projected_overall_picks": positions,
                "selection": selection,
                "capital_index": sum(100 / math.sqrt(p) for p in positions)
                / len(positions),
            }

        all_slots = list(range(1, count + 1))
        conditional = slots.get(pick["original_roster"])
        selected = (
            conditional
            if order_rule == "reverse_standings" and conditional
            else all_slots
        )
        pick["value_scenario"] = summarize(selected)
        pick["value_scenario"]["basis"] = (
            "current reverse standings"
            if selected is conditional
            else "equal weight across all draft slots"
        )
        pick["value_scenario"]["index_low"] = 100 / math.sqrt(pick["overall_latest"])
        pick["value_scenario"]["index_high"] = 100 / math.sqrt(pick["overall_earliest"])
        pick["value_scenario"]["reverse_standings_if_season_ended_today"] = (
            summarize(conditional) if conditional else None
        )
    return inventory
