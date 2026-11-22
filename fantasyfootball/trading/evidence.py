"""Forecast freshness and explicit sensitivity checks for roster decisions.

Appearance rates describe history, not medical clearance. Scenario bounds are
assumptions, not confidence intervals or validated replacement forecasts.
"""

import pandas as pd

from fantasyfootball.trading.value import RestOfSeasonValue


def player_evidence(roster, history, schedule, details, season, week):
    past = history.loc[history.season * 100 + history.week < season * 100 + week]
    games = schedule.loc[
        schedule.season.eq(season) & schedule.week.lt(week)
        & schedule.game_type.eq("REG")
    ]
    evidence = {}
    for row in roster.itertuples():
        observed = past.loc[past.player_id.eq(row.player_id)].sort_values(["season", "week"])
        current = observed.loc[observed.season.eq(season) & observed.team.eq(row.team)]
        expected = set(games.loc[games.home_team.eq(row.team) | games.away_team.eq(row.team), "week"])
        last = int(current.week.max()) if not current.empty else None
        gap = sum(w > last for w in expected) if last is not None else len(expected)
        injury = details.get(str(row.sleeper_id), {}).get("injury_status")
        flags = []
        if len(observed) < 4:
            flags.append("low_sample")
        if gap:
            flags.append("missing_recent_games")
        if gap and not injury:
            flags.append("workload_after_gap_unverified")
        if injury:
            flags.append("injury_designation")
        recent = observed.tail(12).fantasy_points if "fantasy_points" in observed else pd.Series(dtype=float)
        evidence[str(row.player_id)] = {
            "last_observed_period": int(observed.iloc[-1].season * 100 + observed.iloc[-1].week) if not observed.empty else None,
            "history_games": len(observed), "scheduled_games_since_observation": gap,
            "injury_status": injury, "flags": flags,
            "historical_workload_points": float(recent.mean()) if len(recent) else None,
        }
    return evidence


def assess_drops(roster, owner, projections, replacements, alternatives, participation,
                 slots, weeks, evidence, *, keeper_limit=0, incoming=None, samples=128):
    """Compare legal drops with shared draws, optionally after an acquisition.

    A one-point full-horizon tolerance is a presentation rule, not significance.
    Keeper leagues receive no unconditional drop advice from a ROS-only model.
    """
    owned = roster.loc[roster.roster_id.eq(owner)]
    ids = set(owned.player_id)
    if incoming is not None:
        if incoming in ids or incoming not in set(roster.player_id):
            raise ValueError("Incoming player must belong to a different roster")
        ids.add(incoming)
    candidates = list(owned.loc[owned.tradable, "player_id"])
    affected = [p for p in ids if "workload_after_gap_unverified" in evidence.get(p, {}).get("flags", [])]
    scenarios = [("historical_participation", projections.copy(), participation.copy())]
    if affected:
        healthy = participation.copy()
        healthy.loc[healthy.player_id.isin(affected), "probability"] = 1.0
        scenarios.append(("full_availability_current_workload", projections.copy(), healthy))
        restored = projections.copy()
        for pid in affected:
            workload = evidence[pid]["historical_workload_points"]
            mask = restored.player_id.eq(pid) & restored.status.eq("projected")
            if workload is not None:
                restored.loc[mask, "projected_points"] = restored.loc[mask, "projected_points"].clip(lower=workload)
        scenarios.append(("full_availability_historical_workload", restored, healthy.copy()))
    losses = {pid: {} for pid in candidates}
    for label, frame, rates in scenarios:
        model = RestOfSeasonValue(roster, frame, replacements, alternatives, rates, slots, weeks, samples=samples)
        base = model.total(ids)
        if base is None:
            return {"status": "incomplete", "reason": "Unknown player-week forecasts; no drop recommendation", "candidates": []}
        for pid in candidates:
            losses[pid][label] = max(0.0, base - model.total(ids - {pid}))
    best = {label: min((losses[p][label] for p in candidates), default=0) for label, _, _ in scenarios}
    rows = []
    for pid in candidates:
        player = owned.loc[owned.player_id.eq(pid)].iloc[0]
        flags = evidence.get(pid, {}).get("flags", [])
        rows.append({"player_id": pid, "name": player.get("player_name", pid),
                     "position": player.pos, "scenario_losses": losses[pid],
                     "loss_low": min(losses[pid].values()), "loss_high": max(losses[pid].values()),
                     "near_best_in_all_scenarios": all(losses[pid][s] <= best[s] + 1 for s in best),
                     "flags": flags,
                     "bye_weeks": projections.loc[projections.player_id.eq(pid) & projections.status.eq("bye"), "week"].astype(int).tolist()})
    rows.sort(key=lambda r: (r["loss_high"], r["player_id"]))
    shortlist = [r["player_id"] for r in rows if r["near_best_in_all_scenarios"]]
    review = keeper_limit > 0 or any(evidence.get(p, {}).get("flags") for p in ids)
    return {"status": "review_required" if review else "near_tie" if len(shortlist) != 1 else "scenario_stable",
            "recommended_player_id": shortlist[0] if not review and len(shortlist) == 1 else None,
            "shortlist": shortlist, "candidates": rows, "incoming_player_id": incoming,
            "keeper_review_required": keeper_limit > 0,
            "near_tie_tolerance_points": 1.0,
            "scenario_basis": "Historical participation versus full availability and a trailing-12-game workload floor for players with unverified workload after missing games. Sensitivities, not confidence intervals.",
            "replacement_assumption": "Weekly waiver access assumed; competition and reacquisition costs excluded"}
