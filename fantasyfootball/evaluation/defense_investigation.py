"""Reproduce defense source comparisons and optional play-level attribution audits."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd

from fantasyfootball.evaluation.defense import DefenseScoringAudit
from fantasyfootball.evaluation.defense_reconciliation import (
    DefenseComponentReconciliation,
)
from fantasyfootball.evaluation.defense_triage import DefenseDiscrepancyTriage


def investigate(
    team_stats,
    settings,
    records,
    *,
    season,
    through_week,
    pbp=None,
    complete_game_ids=(),
):
    coverage, candidates = DefenseScoringAudit().audit(
        team_stats, settings, season=season, through_week=through_week
    )
    reconciliation, comparisons = DefenseComponentReconciliation().compare(
        candidates, records, season=season, through_week=through_week
    )
    triage, cases = DefenseDiscrepancyTriage().triage(comparisons, team_stats, records)
    reports = {"coverage": coverage, "reconciliation": reconciliation, "triage": triage}
    tables = {
        "candidate-components": candidates,
        "component-comparisons": comparisons,
        "discrepancy-cases": cases,
    }
    if pbp is not None:
        from fantasyfootball.evaluation.defense_events import DefenseEventAudit

        audit, derived, events = DefenseEventAudit().audit(
            pbp,
            season=season,
            through_week=through_week,
            complete_game_ids=complete_game_ids,
        )
        report, comparison = DefenseComponentReconciliation().compare(
            derived, records, season=season, through_week=through_week
        )
        reports.update(events=audit, event_reconciliation=report)
        tables.update(
            event_components=derived, event_ledger=events, event_comparisons=comparison
        )
    return reports, tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["team-stats", "settings", "sleeper-stats", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pbp", type=Path)
    parser.add_argument(
        "--complete-game-ids",
        type=Path,
        help="JSON list of game IDs whose full PBP coverage was independently checked; omitted means unverified",
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.complete_game_ids and not args.pbp:
        parser.error("--complete-game-ids requires --pbp")
    settings = json.loads(args.settings.read_text(encoding="utf-8-sig"))
    complete = (
        json.loads(args.complete_game_ids.read_text(encoding="utf-8-sig"))
        if args.complete_game_ids
        else []
    )
    if not isinstance(complete, list) or any(
        not isinstance(v, str) or not v.strip() for v in complete
    ):
        raise ValueError("Complete game IDs must be a JSON list of nonempty strings")
    reports, tables = investigate(
        pd.read_csv(args.team_stats),
        settings.get("scoring_settings", settings),
        json.loads(args.sleeper_stats.read_text(encoding="utf-8-sig")),
        season=args.season,
        through_week=args.through_week,
        pbp=pd.read_csv(args.pbp, low_memory=False) if args.pbp else None,
        complete_game_ids=complete,
    )
    paths = {
        name: getattr(args, name)
        for name in [
            "team_stats",
            "settings",
            "sleeper_stats",
            "pbp",
            "complete_game_ids",
        ]
    }
    hashes = {
        name: sha256(path.read_bytes()).hexdigest()
        for name, path in paths.items()
        if path
    }
    args.output.mkdir(parents=True, exist_ok=False)
    for name, report in reports.items():
        report["input_sha256"] = hashes
        (args.output / (name + ".json")).write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
    for name, table in tables.items():
        table.to_csv(args.output / (name + ".csv"), index=False)
    print(json.dumps({"reports": sorted(reports), "ready_for_scoring": False}))


if __name__ == "__main__":
    main()
