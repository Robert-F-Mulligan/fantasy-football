"""Score the earliest sealed trade capture per origin in the private repository."""

import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from fantasyfootball.archives.evidence import timestamp, verify
from fantasyfootball.core.domain import ScoringRules
from fantasyfootball.evaluation.trades import evaluate_trade_forecasts


def settled_trade_outcomes(document, current, schedule, scoring):
    season = document["season"]
    completed, outcomes = set(), {}
    for week in document["weeks"]:
        games = schedule.loc[
            schedule.season.eq(season)
            & schedule.week.eq(week)
            & schedule.game_type.eq("REG")
        ]
        if games.empty or games[["home_score", "away_score"]].isna().any().any():
            continue
        starts = (
            pd.to_datetime(
                games.gameday + " " + games.gametime, format="%Y-%m-%d %H:%M"
            )
            .dt.tz_localize("America/New_York")
            .dt.tz_convert("UTC")
        )
        if starts.max() + pd.Timedelta(hours=8) > timestamp(
            current.manifest["captured_at"]
        ):
            continue
        raw = current.history.loc[
            current.history.season.eq(season) & current.history.week.eq(week)
        ]
        if raw.player_id.duplicated().any():
            raise ValueError("Duplicate trade outcome player-week")
        if not (set(games.home_team) | set(games.away_team)).issubset(set(raw.team)):
            continue
        completed.add(week)
        points = ScoringRules(scoring).score(raw)
        for pid, value in zip(raw.player_id, points):
            outcomes[(str(pid), week)] = float(value)
    return outcomes, completed


def build_private_trade_scorecards(current, checkout, schedule, league):
    checkout = Path(checkout)
    chosen = {}
    for path in sorted((checkout / "snapshots").glob("*/week-*/*.zip")):
        if not path.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Trade archive path escapes repository")
        with ZipFile(path) as archive:
            if "plan/trade-prospective.json" not in archive.namelist():
                continue
            manifest = json.loads(archive.read("evidence-manifest.json"))
            settings = json.loads(archive.read("league/import-report.json"))
        if (settings["league_id"], settings["roster_id"]) != league:
            continue
        captured = timestamp(manifest["captured_at"])
        if captured > timestamp(current.manifest["captured_at"]):
            continue
        period = (manifest["season"], manifest["week"])
        order = (captured, path.name)
        if period not in chosen or order < chosen[period][0]:
            chosen[period] = (order, path)
    added = []
    scope = hashlib.sha256(json.dumps(league).encode()).hexdigest()[:16]
    for _, path in chosen.values():
        manifest = verify(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with ZipFile(path) as archive:
            document = json.loads(archive.read("plan/trade-prospective.json"))
            scoring = json.loads(archive.read("league/league-supported-offense.json"))[
                "scoring"
            ]
        if (document["season"], document["origin_week"]) != (
            manifest["season"],
            manifest["week"],
        ):
            raise ValueError("Trade protocol does not match archive origin")
        outcomes, completed = settled_trade_outcomes(
            document, current, schedule, scoring
        )
        report = evaluate_trade_forecasts(
            document, outcomes, completed, manifest["captured_at"]
        )
        report.update(
            forecast_archive_sha256=digest,
            outcome_archive_sha256=current.sha256,
            selection_policy="Earliest retained trade capture per league/origin, including late captures; never replace with a better rerun",
        )
        relative = (
            Path("trade-scorecards")
            / scope
            / str(document["season"])
            / f"week-{document['origin_week']:02d}"
            / f"{digest}-{current.sha256}.json"
        )
        target = checkout / relative
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Trade scorecard path escapes repository")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
            )
            added.append(relative.as_posix())
    return added
