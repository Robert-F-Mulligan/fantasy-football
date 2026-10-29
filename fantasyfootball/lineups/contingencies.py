"""One-player injury contingencies using exact league slots and kickoff locks."""

import pandas as pd

from fantasyfootball.lineups.optimization import LineupOptimizer


def injury_flag(row):
    status = row.get("injury_status")
    if pd.notna(status) and str(status).strip():
        return str(status).casefold()
    warning = str(row.get("warning", "")).casefold()
    return "questionable" if "questionable" in warning else ""


def injury_contingencies(board, lineup, slots, as_of):
    """Keep unaffected starters; evaluate one healthy bench addition per scenario.

    Later options remain available until the injured starter's kickoff. Earlier
    options require deciding before the backup's kickoff. These are independent
    scenarios, not a plan for multiple simultaneous absences.
    """
    now = pd.to_datetime(as_of, utc=True, errors="coerce")
    if pd.isna(now) or not slots or set(slots) != set(lineup.slot):
        return []
    roster = board.copy()
    roster["kickoff"] = pd.to_datetime(roster.get("kickoff"), utc=True, errors="coerce")
    roster["projected_points"] = pd.to_numeric(roster.projected_points, errors="coerce")
    selected = set(lineup.player_id)
    assigned = lineup.set_index("player_id").slot.to_dict()
    starters = roster.loc[roster.player_id.isin(selected)]
    bench = roster.loc[
        ~roster.player_id.isin(selected)
        & roster.availability.eq("eligible")
        & roster.kickoff.gt(now)
        & roster.projected_points.notna()
    ]
    bench = bench.loc[~bench.apply(injury_flag, axis=1).astype(bool)]
    scenarios = []
    for out in starters.to_dict("records"):
        if injury_flag(out) != "questionable" or out["availability"] != "eligible":
            continue
        if pd.isna(out["kickoff"]) or out["kickoff"] <= now:
            continue
        options = []
        retained = starters.loc[starters.player_id.ne(out["player_id"])]
        for candidate in bench.to_dict("records"):
            deadline = min(candidate["kickoff"], out["kickoff"])
            fixed = {
                row.player_id: assigned[row.player_id]
                for row in retained.itertuples()
                if row.availability == "locked_starter"
                or pd.isna(row.kickoff)
                or row.kickoff <= deadline
            }
            pool = pd.concat([retained, pd.DataFrame([candidate])], ignore_index=True)
            try:
                alternative = LineupOptimizer().optimize(
                    pool, slots, fixed_slots={slot: pid for pid, slot in fixed.items()}
                )
            except ValueError:
                continue
            changes = [
                {
                    "player_name": row.player_name,
                    "from_slot": assigned.get(row.player_id),
                    "slot": row.slot,
                }
                for row in alternative.itertuples()
                if assigned.get(row.player_id) != row.slot
            ]
            options.append(
                {
                    "player_name": candidate["player_name"],
                    "player_id": candidate["player_id"],
                    "projected_points": candidate["projected_points"],
                    "deadline": deadline,
                    "later": candidate["kickoff"] >= out["kickoff"],
                    "assignments": changes,
                }
            )
        options.sort(
            key=lambda row: (
                not row["later"],
                -row["projected_points"],
                str(row["player_id"]),
            )
        )
        scenarios.append(
            {"starter": out["player_name"], "option": options[0] if options else None}
        )
    return scenarios
