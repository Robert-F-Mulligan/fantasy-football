"""Next-season draft assets, preserving original roster identity and current ownership."""

from datetime import datetime, timezone


def fetch_pick_inventory(league_id, season, client=None, *, confirmed_rounds=None):
    from fantasyfootball.data.sleeper import SleeperClient

    client = client or SleeperClient()
    prefix = f"league/{league_id}"
    league = client.get(prefix)
    if str(league.get("season")) != str(season):
        raise ValueError("Pick inventory league season does not match")
    rosters = client.get(prefix + "/rosters")
    traded = client.get(prefix + "/traded_picks")
    drafts = client.get(prefix + "/drafts")
    owners = sorted(int(row["roster_id"]) for row in rosters)
    if not owners or len(owners) != len(set(owners)):
        raise ValueError("Pick inventory requires unique league rosters")
    year = season + 1
    future = [d for d in drafts if str(d.get("season")) == str(year)]
    previous = [
        d
        for d in drafts
        if str(d.get("season")) == str(season) and d.get("status") == "complete"
    ]
    candidates = future or previous
    inventory = {
        "league_id": str(league_id),
        "as_of": datetime.now(timezone.utc).isoformat(),
        "season": year,
        "picks": [],
        "status": "unavailable",
        "trades_disabled": bool(league.get("settings", {}).get("disable_trades", 0)),
    }
    if len(candidates) != 1:
        inventory["reason"] = (
            "No unique draft configuration; pick inventory needs league rules"
        )
        return inventory
    draft = candidates[0]
    if draft.get("type") not in {"snake", "linear"}:
        inventory["reason"] = (
            "Draft format does not support numbered-round pick scenarios"
        )
        return inventory
    rounds = int(draft.get("settings", {}).get("rounds", 0))
    if confirmed_rounds is not None:
        if (
            isinstance(confirmed_rounds, bool)
            or not isinstance(confirmed_rounds, int)
            or not 1 <= confirmed_rounds <= 50
        ):
            raise ValueError("Confirmed draft rounds must be an integer from 1 to 50")
        if future and rounds != confirmed_rounds:
            raise ValueError(
                "Confirmed rounds conflict with the configured next-year draft"
            )
        rounds = confirmed_rounds
    teams = int(draft.get("settings", {}).get("teams", 0))
    if not 1 <= rounds <= 50 or teams != len(owners):
        raise ValueError("Draft round/team configuration is incomplete")
    if future and draft.get("status") in {"drafting", "complete"}:
        inventory["reason"] = "Next-year draft has already started"
        return inventory
    assets = {}
    for round_number in range(1, rounds + 1):
        for owner in owners:
            key = f"{year}:{round_number}:{owner}"
            assets[key] = {
                "pick_id": key,
                "season": year,
                "round": round_number,
                "original_roster": owner,
                "owner_id": owner,
                "overall_earliest": (round_number - 1) * teams + 1,
                "overall_latest": round_number * teams,
            }
    seen = set()
    for row in traded:
        if str(row["season"]) != str(year):
            continue
        key = f"{year}:{int(row['round'])}:{int(row['roster_id'])}"
        if key in seen or key not in assets or int(row["owner_id"]) not in owners:
            raise ValueError("Conflicting or invalid traded-pick ownership")
        assets[key]["owner_id"] = int(row["owner_id"])
        seen.add(key)
    inventory.update(
        status="configured"
        if future
        else "rounds_confirmed"
        if confirmed_rounds is not None
        else "provisional",
        rounds=rounds,
        source_season=int(draft["season"]),
        draft_type=draft["type"],
        picks=list(assets.values()),
        round_setting=league.get("settings", {}).get("draft_rounds"),
        order_status="unassigned; full round range, not a probability interval",
        valuation_status="unpriced; keeper costs and next-year player pool not modeled",
    )
    return inventory


def validate_pick_exchange(inventory, my_roster, partner_roster, give, receive):
    if not give and not receive:
        return [], []
    if not inventory or inventory.get("status") not in {
        "configured",
        "provisional",
        "rounds_confirmed",
    }:
        raise ValueError("A usable next-year pick inventory is required")
    if inventory.get("trades_disabled"):
        raise ValueError("League trades are disabled")
    if len(set(give + receive)) != len(give + receive):
        raise ValueError("Pick IDs must be unique across both sides")
    assets = {row["pick_id"]: row for row in inventory["picks"]}
    for ids, owner in [(give, my_roster), (receive, partner_roster)]:
        if any(pid not in assets or assets[pid]["owner_id"] != owner for pid in ids):
            raise ValueError(
                "Every draft pick must be owned by its specified trade side"
            )
    return [dict(assets[pid]) for pid in give], [dict(assets[pid]) for pid in receive]
