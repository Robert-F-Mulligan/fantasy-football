"""Standings-based search priority, not a model of managers' trade acceptance."""

import math


def prioritize_pick_targets(targets, roster, inventory, my_roster, limit=5):
    standings = (inventory or {}).get("standings_snapshot", [])
    owners = {int(x) for x in roster.roster_id}
    by_owner = {int(row["roster_id"]): row for row in standings}
    usable = len(by_owner) == len(standings) and owners == set(by_owner)
    usable = usable and all(
        isinstance(r.get("win_fraction"), (int, float))
        and math.isfinite(r["win_fraction"])
        and 0 <= r["win_fraction"] <= 1
        for r in standings
    )
    cutoff = (
        sorted(r["win_fraction"] for r in standings)[math.ceil(len(standings) / 3) - 1]
        if usable and standings
        else None
    )
    # An all-tied league provides no evidence of weaker-record sellers.
    focused = cutoff is not None and cutoff < max(r["win_fraction"] for r in standings)
    priority = {
        owner
        for owner, row in by_owner.items()
        if focused and row["win_fraction"] <= cutoff and owner != my_roster
    }
    player_owners = roster.set_index("player_id").roster_id.to_dict()
    decorated = []
    for target in targets:
        owner = int(player_owners[target["player_id"]])
        standing = by_owner.get(owner, {}) if usable else {}
        decorated.append(
            {
                **target,
                "seller": {
                    "roster_id": owner,
                    "priority": owner in priority,
                    "win_fraction": standing.get("win_fraction"),
                    "record": standing.get("record"),
                },
            }
        )
    decorated.sort(
        key=lambda t: (
            not t["seller"]["priority"],
            -t["marginal_ros_gain"],
            t["player_id"],
        )
    )
    return decorated[:limit], {
        "status": "record_focus" if priority else "value_only",
        "priority_roster_ids": sorted(priority),
        "as_of": (inventory or {}).get("as_of"),
        "policy": "Bottom third by win percentage, including boundary ties; prioritize positive roster-value gains within that group, then other teams",
        "interpretation": "Record-based outreach priority only; rebuilding intent and willingness to accept picks are unknown",
    }
