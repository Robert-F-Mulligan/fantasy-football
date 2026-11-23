"""Verified private status observations and conservative prospective follow-up."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from fantasyfootball.archives.evidence import timestamp, verify


def read_observations(path):
    manifest = verify(path)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with ZipFile(path) as archive:
        settings = json.loads(archive.read("league/import-report.json"))
        from fantasyfootball.evaluation.scorecard import scoring_digest
        scoring = json.loads(archive.read("league/league-supported-offense.json"))["scoring"]
        context = json.loads(archive.read("context/manifest.json"))
        details = json.loads(archive.read("context/players.json"))
        roster = pd.read_csv(io.BytesIO(archive.read("plan/availability.csv")), dtype={"sleeper_id": str, "player_id": str})
        projections = pd.read_csv(io.BytesIO(archive.read("plan/projections.csv")), dtype={"player_id": str})
    fetched = timestamp(context["players.json"]["fetched_at"])
    captured = timestamp(manifest["captured_at"])
    if fetched > captured:
        raise ValueError("Player status was fetched after archive capture")
    if projections.player_id.dropna().duplicated().any():
        raise ValueError("Duplicate forecast identity")
    scores = projections.set_index("player_id").projected_points.to_dict()
    eligibility = {r["sleeper_id"]: r for r in manifest["eligibility"]}
    rows = []
    for row in roster.to_dict("records"):
        if row.get("pos") not in {"QB", "RB", "WR", "TE"}:
            continue
        if "roster_id" in row and row["roster_id"] != settings["roster_id"]:
            continue
        pid = row.get("player_id")
        if pd.isna(pid):
            continue
        sid = row["sleeper_id"]
        player = details.get(sid, {})
        known = "injury_status" in player
        designation = player.get("injury_status")
        designation = str(designation).strip().lower() if designation else None
        points = scores.get(pid)
        rows.append({
            "league_id": str(settings["league_id"]), "roster_id": settings["roster_id"],
            "season": manifest["season"], "week": manifest["week"],
            "player_id": pid, "sleeper_id": sid,
            "captured_at": captured.isoformat(), "provider_fetched_at": fetched.isoformat(),
            "source_archive_sha256": digest, "scoring_sha256": scoring_digest(scoring),
            "pregame": eligibility[sid]["pregame_evidence"],
            "eligibility_reason": eligibility[sid]["reason"],
            "kickoff": str(row["kickoff"]) if pd.notna(row.get("kickoff")) else None,
            "injury_field_present": known, "injury_designation": designation,
            "provider_status": player.get("status"),
            "practice_participation": player.get("practice_participation"),
            "practice_description": player.get("practice_description"),
            "model_eligibility": row.get("availability"),
            "projected_points": float(points) if pd.notna(points) else None,
            "confirmed_game_active": None,
        })
    return rows


def designation_history(observations):
    """Keep missing fields distinct from an explicitly empty designation."""
    previous, rows = {}, []
    for source in sorted(observations, key=lambda r: (timestamp(r["captured_at"]), r["source_archive_sha256"], r["sleeper_id"])):
        row = dict(source)
        key = (row["league_id"], row["roster_id"], row["sleeper_id"])
        prior = previous.get(key)
        row["designation_removed"] = False
        row["previous_status_archive_sha256"] = None
        if prior and timestamp(row["provider_fetched_at"]) > timestamp(prior["provider_fetched_at"]):
            row["previous_status_archive_sha256"] = prior["source_archive_sha256"]
            row["designation_removed"] = bool(
                prior["injury_field_present"] and prior["injury_designation"]
                and row["injury_field_present"] and not row["injury_designation"]
            )
        if prior is None or timestamp(row["provider_fetched_at"]) > timestamp(prior["provider_fetched_at"]):
            previous[key] = row
        rows.append(row)
    return rows


def follow_up(observations, outcomes):
    """Earliest capture per player/week, chosen without looking at outcomes.

    Outcome mappings contain only explicitly settled records; absent keys are
    unresolved. A status field alone is never a confirmed game-day active list.
    """
    chosen = {}
    for row in sorted(observations, key=lambda r: (timestamp(r["captured_at"]), r["source_archive_sha256"])):
        key = (row["league_id"], row["roster_id"], row["season"], row["week"], row["player_id"])
        chosen.setdefault(key, row)
    evaluated = []
    for key, row in chosen.items():
        result = dict(row)
        result.update(outcome_status="unresolved", actual_points=None, absolute_error=None)
        outcome = outcomes.get(key)
        if not row["pregame"]:
            result["outcome_status"] = "excluded_late_or_unknown_kickoff"
        elif outcome and row.get("scoring_sha256") and outcome.get("scoring_sha256") != row["scoring_sha256"]:
            result["outcome_status"] = "unresolved"
            result["reason"] = "Outcome scoring differs from the frozen forecast"
        elif outcome:
            if outcome["status"] not in {"played", "dnp"} or not outcome.get("source"):
                raise ValueError("Outcome requires explicit finalized evidence")
            if timestamp(outcome["finalized_at"]) <= timestamp(row["kickoff"]):
                raise ValueError("Outcome predates kickoff")
            points = float(outcome["points"])
            if not pd.notna(points) or abs(points) == float("inf"):
                raise ValueError("Outcome points must be finite")
            if outcome["status"] == "dnp" and points != 0:
                raise ValueError("Confirmed DNP must have zero points")
            result.update(outcome_status=outcome["status"], actual_points=points,
                          outcome_source=outcome["source"])
            if row["projected_points"] is not None:
                result["absolute_error"] = abs(row["projected_points"]-points)
        evaluated.append(result)
    errors = [r["absolute_error"] for r in evaluated if r["absolute_error"] is not None]
    return {"protocol": "availability_observations_v1", "observations": observations,
            "selected_forecasts": evaluated, "selected_count": len(evaluated),
            "scored_count": len(errors),
            "unresolved_count": sum(r["outcome_status"] == "unresolved" for r in evaluated),
            "mae_observed_only": sum(errors)/len(errors) if errors else None,
            "selection_policy": "Earliest retained capture per league/roster/player/week, including late captures; no substitution of later forecasts",
            "limits": ["Fetched time records observation, not the provider publication time",
                       "Designation removed is not medical clearance or confirmed game-day activity",
                       "Missing box scores remain unresolved, never inferred DNP or zero",
                       "Observed-only MAE is descriptive and subject to coverage bias; no significance or promotion claim"]}


def build_private_availability_history(current, checkout, schedule, league):
    from fantasyfootball.evaluation.scorecard import ArchivedForecast
    from fantasyfootball.evaluation.scorecard_archive import observed_outcomes

    checkout = Path(checkout)
    observations, paths = [], {}
    for path in sorted((checkout/"snapshots").glob("*/week-*/*.zip")):
        if not path.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Availability archive path escapes repository")
        rows = read_observations(path)
        rows = [r for r in rows if (r["league_id"],r["roster_id"]) == (str(league[0]),league[1])
                and timestamp(r["captured_at"]) <= timestamp(current.manifest["captured_at"])]
        observations.extend(rows)
        for row in rows:
            key = (row["season"],row["week"])
            order = (timestamp(row["captured_at"]),row["source_archive_sha256"])
            if key not in paths or order < paths[key][0]:
                paths[key] = (order,path)
    outcomes = {}
    for _,path in paths.values():
        previous = ArchivedForecast(path)
        document = observed_outcomes(previous,current,schedule)
        if document:
            for row in document["players"]:
                key = (str(league[0]),league[1],document["season"],document["week"],row["player_id"])
                outcomes[key] = {**row, "scoring_sha256": document["scoring_sha256"]}
    report = follow_up(designation_history(observations), outcomes)
    report["outcome_archive_sha256"] = current.sha256
    scope = hashlib.sha256(json.dumps(league).encode()).hexdigest()[:16]
    relative = Path("availability-history")/scope/(current.sha256+".json")
    target = checkout/relative
    if not target.resolve().is_relative_to(checkout.resolve()):
        raise ValueError("Availability output escapes repository")
    if target.exists():
        return []
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,indent=2,allow_nan=False)
    return [relative.as_posix()]
