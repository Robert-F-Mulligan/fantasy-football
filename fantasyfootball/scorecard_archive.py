"""Create private scorecards from prior captures and later completed-week stats."""

import hashlib
import json
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from .domain import ScoringRules
from .evidence import timestamp
from .scorecard import (
    ArchivedForecast,
    WeeklyScorecard,
    scoring_digest,
    write_scorecard,
)


def observed_outcomes(previous, current, schedule):
    season, week = previous.manifest["season"], previous.manifest["week"]
    if (
        season * 100 + week
        >= current.manifest["season"] * 100 + current.manifest["week"]
    ):
        return None
    games = schedule.loc[
        schedule.season.eq(season)
        & schedule.week.eq(week)
        & schedule.game_type.eq("REG")
    ]
    if games.empty or games[["home_score", "away_score"]].isna().any().any():
        return None
    kickoff = (
        pd.to_datetime(games.gameday + " " + games.gametime, format="%Y-%m-%d %H:%M")
        .dt.tz_localize("America/New_York")
        .dt.tz_convert("UTC")
    )
    if kickoff.isna().any() or kickoff.max() + pd.Timedelta(hours=8) > timestamp(
        current.manifest["captured_at"]
    ):
        return None
    raw = current.history.loc[
        current.history.season.eq(season) & current.history.week.eq(week)
    ].copy()
    if raw.player_id.duplicated().any():
        raise ValueError("Duplicate finalized player-game rows")
    if not (set(games.home_team) | set(games.away_team)).issubset(set(raw.team)):
        return None
    raw["points"] = ScoringRules(previous.scoring).score(raw)
    source = "Archived nflverse observed box scores from snapshot " + current.sha256
    players = [
        {
            "player_id": str(row.player_id),
            "status": "played",
            "points": float(row.points),
            "source": source,
            "finalized_at": current.manifest["captured_at"],
        }
        for row in raw.itertuples()
    ]
    return {
        "season": season,
        "week": week,
        "scoring_sha256": scoring_digest(previous.scoring),
        "players": players,
    }


def build_private_scorecards(current_archive, checkout):
    """Choose the earliest saved capture per league/week, before inspecting outcomes."""
    checkout = Path(checkout)
    current = ArchivedForecast(current_archive)
    with ZipFile(current_archive) as archive:
        import io

        schedule = pd.read_csv(io.BytesIO(archive.read("context/games.csv")))
        settings = json.loads(archive.read("league/import-report.json"))
        league = (settings["league_id"], settings["roster_id"])
    chosen = {}
    for path in sorted((checkout / "snapshots").glob("*/week-*/*.zip")):
        if not path.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Private snapshot path escapes repository")
        with ZipFile(path) as archive:
            metadata = json.loads(archive.read("evidence-manifest.json"))
            settings = json.loads(archive.read("league/import-report.json"))
            owner = (settings["league_id"], settings["roster_id"])
        if owner != league:
            continue
        period = (metadata["season"], metadata["week"])
        order = (timestamp(metadata["captured_at"]), path.name)
        if period not in chosen or order < chosen[period][0]:
            chosen[period] = (order, path)
    added = []
    for _, path in chosen.values():
        previous = ArchivedForecast(path)
        outcomes = observed_outcomes(previous, current, schedule)
        if outcomes is None:
            continue
        report, rows = WeeklyScorecard().evaluate(previous, outcomes)
        outcome_bytes = json.dumps(outcomes, sort_keys=True).encode()
        report["outcomes_sha256"] = hashlib.sha256(outcome_bytes).hexdigest()
        report["selection_policy"] = (
            "Earliest retained capture for this league/week, including late captures; no cherry-picking reruns"
        )
        report["outcome_archive_sha256"] = current.sha256
        relative = (
            Path("scorecards")
            / str(report["season"])
            / f"week-{report['week']:02d}"
            / f"{previous.sha256}-{current.sha256}.zip"
        )
        target = checkout / relative
        if not target.resolve().is_relative_to(checkout.resolve()):
            raise ValueError("Private scorecard path escapes repository")
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ff-scorecard-") as directory:
            output = Path(directory) / "result"
            write_scorecard(report, rows, output)
            (output / "outcomes.json").write_bytes(outcome_bytes)
            with ZipFile(target, "x", compression=ZIP_DEFLATED) as archive:
                for file in sorted(output.iterdir()):
                    archive.write(file, file.name)
        added.append(relative.as_posix())
    return added
