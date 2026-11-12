"""Concrete player-for-owned-pick proposals, including the necessary roster drop."""


def pick_trade_scenarios(calculator, my_roster, target_ids, rounds=(1, 2, 3)):
    inventory = calculator.pick_inventory
    if not inventory or inventory.get("status") not in {
        "configured",
        "rounds_confirmed",
        "provisional",
    }:
        return {
            "status": "unavailable",
            "reason": "Refresh next-year pick ownership",
            "offers": [],
        }
    if inventory.get("trades_disabled"):
        return {
            "status": "unavailable",
            "reason": "League pick trades are disabled",
            "offers": [],
        }
    picks = sorted(
        [
            p
            for p in inventory["picks"]
            if p["owner_id"] == my_roster and p["round"] in rounds
        ],
        key=lambda p: (p["round"], p["original_roster"]),
    )
    drops = sorted(
        calculator.roster.loc[
            calculator.roster.roster_id.eq(my_roster) & calculator.roster.tradable,
            "player_id",
        ]
    )
    offers = []
    for target_id in dict.fromkeys(map(str, target_ids)):
        if target_id not in calculator.players.index:
            continue
        target = calculator.players.loc[target_id]
        if target.roster_id == my_roster or not target.tradable:
            continue
        for pick in picks:
            candidates = []
            for drop in drops:
                result = calculator.evaluate(
                    my_roster,
                    int(target.roster_id),
                    [],
                    [target_id],
                    my_drops=[drop],
                    give_picks=[pick["pick_id"]],
                )
                if result["status"] == "estimated":
                    candidates.append(result)
            if not candidates:
                offers.append(
                    {
                        "target_id": target_id,
                        "pick": pick,
                        "status": "unavailable",
                        "reason": "Incomplete current-season roster forecasts",
                    }
                )
                continue
            # Prefer the best ROS lineup. For equal ROS gains, preserve future keeper utility.
            best = max(
                candidates,
                key=lambda r: (
                    r["my_gain"],
                    r.get("offer_estimate", {})
                    .get("my_total_change", {})
                    .get("low", float("-inf")),
                    tuple(r["my_drops"]),
                ),
            )
            estimate = best.get("offer_estimate", {})
            reference = next(
                (
                    s
                    for s in estimate.get("scenarios", [])
                    if s["rank_shift"] == 0
                    and s["future_weight"] == 1
                    and s["keeper_mode"]
                    == (
                        "latest"
                        if calculator.offer_fairness.evidence["keeper_limit"]
                        else "none"
                    )
                ),
                None,
            )
            if estimate.get("status") != "conditional_estimate":
                decision = "unpriced"
            else:
                me, partner = (
                    estimate["my_total_change"],
                    estimate["partner_total_change"],
                )
                if me["high"] < 0:
                    decision = "too_expensive"
                elif me["low"] > 0 and partner["high"] < 0:
                    decision = "seller_loses"
                elif me["low"] > 0 and partner["low"] > 0:
                    decision = "both_benefit"
                elif me["low"] > 0:
                    decision = "positive_for_you"
                else:
                    decision = "conditional"
            offers.append(
                {
                    "target_id": target_id,
                    "pick": pick,
                    "status": "estimated",
                    "decision": decision,
                    "reference": reference,
                    "trade": best,
                }
            )
    return {
        "status": "estimated",
        "season": inventory["season"],
        "offers": offers,
        "reference_assumption": "Current standings, latest keeper round minus two, equal weight on current and next-year point-equivalents",
        "drop_policy": "Highest remaining-season lineup value, then highest worst-scenario two-season value among equal ROS choices",
    }
