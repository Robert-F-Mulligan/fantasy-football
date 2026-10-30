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
    prepared = _prepare(board, lineup, slots, as_of)
    if prepared is None:
        return []
    now, assigned, starters, bench = prepared
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


def _prepare(board, lineup, slots, as_of):
    now = pd.to_datetime(as_of, utc=True, errors="coerce")
    if pd.isna(now) or not slots or set(slots) != set(lineup.slot):
        return None
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
    return now, assigned, starters, bench


def combined_injury_contingency(board, lineup, slots, as_of):
    """Find a unique-player plan if every questionable starter is ruled out.

    Prefer waiting until the earliest affected starter's kickoff. If that is
    infeasible, inspect earlier bench kickoffs from latest to earliest. This is a
    conditional plan made before that deadline, not a forecast of injury news.
    """
    prepared = _prepare(board, lineup, slots, as_of)
    if prepared is None:
        return None
    now, assigned, starters, bench = prepared
    affected = starters.loc[
        starters.apply(injury_flag, axis=1).eq("questionable")
        & starters.availability.eq("eligible")
        & starters.kickoff.gt(now)
    ]
    if len(affected) < 2:
        return None
    result = {"starters": affected.player_name.tolist(), "status": "unavailable"}
    retained = starters.loc[~starters.player_id.isin(affected.player_id)]
    earliest = affected.kickoff.min()
    deadlines = sorted(
        {earliest, *bench.loc[bench.kickoff.lt(earliest), "kickoff"]}, reverse=True
    )
    for deadline in deadlines:
        pool = pd.concat(
            [retained, bench.loc[bench.kickoff.ge(deadline)]], ignore_index=True
        )
        fixed = {
            assigned[row.player_id]: row.player_id
            for row in retained.itertuples()
            if row.availability == "locked_starter"
            or pd.isna(row.kickoff)
            or row.kickoff <= deadline
        }
        try:
            alternative = LineupOptimizer().optimize(
                pool,
                slots,
                locked=retained.player_id.tolist(),
                fixed_slots=fixed,
                prefer_late_flex=True,
            )
        except ValueError:
            continue
        additions = alternative.loc[~alternative.player_id.isin(retained.player_id)]
        result.update(
            status="ready",
            deadline=deadline,
            earlier=deadline < earliest,
            backups=additions[["player_id", "player_name", "projected_points"]].to_dict(
                "records"
            ),
            assignments=[
                {
                    "player_name": row.player_name,
                    "from_slot": assigned.get(row.player_id),
                    "slot": row.slot,
                }
                for row in alternative.itertuples()
                if assigned.get(row.player_id) != row.slot
            ],
        )
        break
    return result
