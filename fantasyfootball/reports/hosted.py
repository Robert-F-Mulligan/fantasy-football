"""Headless report pipeline for a hosted runner; preparation never sends email."""

import argparse
import contextlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from fantasyfootball.data.data_sync import DataSyncService
from fantasyfootball.reports.reporting import GitHubDeliveryLedger, GmailSMTP, deliver_once, render_report
from fantasyfootball.data.sleeper import SleeperLeagueImporter, load_registry
from fantasyfootball.lineups.weekly import sync_weekly_context, write_weekly_plan


def target_week(schedule, season, now):
    now = pd.Timestamp(now)
    if now.tzinfo is None:
        raise ValueError("Planning time must have a timezone")
    games = schedule.loc[
        (schedule.season == season) & (schedule.game_type == "REG")
    ].copy()
    games["kickoff"] = (
        pd.to_datetime(games.gameday + " " + games.gametime, format="%Y-%m-%d %H:%M")
        .dt.tz_localize("America/New_York")
        .dt.tz_convert("UTC")
    )
    future = games.loc[
        (games.kickoff > now)
        & (games.kickoff <= now.to_pydatetime() + timedelta(days=7))
    ]
    if future.empty:
        return None
    return int(future.sort_values("kickoff").iloc[0].week)


def require_recent_coverage(schedule, history, season, week):
    if week == 1:
        return
    games = schedule.loc[
        (schedule.season == season)
        & (schedule.week == week - 1)
        & (schedule.game_type == "REG")
    ]
    if games.empty or games[["home_score", "away_score"]].isna().any().any():
        raise ValueError(
            "Previous week schedule is incomplete; refusing a stale forecast"
        )
    expected = set(games.home_team) | set(games.away_team)
    observed = set(
        history.loc[(history.season == season) & (history.week == week - 1), "team"]
    )
    if not expected.issubset(observed):
        raise ValueError("Previous week player stats lack one or more scheduled teams")


def prepare(destination, league_id, team_name, season, now=None, archive_dir=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    now = now or datetime.now(timezone.utc)
    context = sync_weekly_context(destination / "context")
    schedule = pd.read_csv(context / "games.csv")
    week = target_week(schedule, season, now)
    if week is None:
        (destination / "delivery.json").write_text(
            json.dumps({"status": "offseason"}), encoding="utf-8"
        )
        return "offseason"
    seasons = list(range(season - 2, season + (week > 1)))
    snapshot, _ = DataSyncService().sync(seasons, season, destination / "data")
    history = pd.read_csv(snapshot / "weekly.csv")
    require_recent_coverage(schedule, history, season, week)
    importer = SleeperLeagueImporter()
    bundle = importer.fetch(league_id, season, team_name, load_registry(snapshot))
    if (
        bundle["report"]["unsupported_slots"]
        or not bundle["report"]["draft_config_supported"]
    ):
        raise ValueError("League configuration is not supported by the hosted planner")
    importer.save(bundle, destination / "league")
    args = SimpleNamespace(
        input=snapshot / "weekly.csv",
        league_dir=destination / "league",
        schedule=context / "games.csv",
        players=context / "players.json",
        season=season,
        week=week,
        as_of=now.isoformat(),
        allow_partial_scoring=True,
        output=destination / "plan",
    )
    with contextlib.redirect_stdout(io.StringIO()):
        write_weekly_plan(args)
    from fantasyfootball.archives.evidence import runtime_provenance

    (args.output / "forecast-provenance.json").write_text(
        json.dumps(runtime_provenance(), indent=2), encoding="utf-8"
    )
    subject, plain, html = render_report(args.output, team_name, season, week)
    (destination / "report.html").write_text(html, encoding="utf-8")
    (destination / "report.txt").write_text(plain, encoding="utf-8")
    (destination / "delivery.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "league_id": league_id,
                "season": season,
                "week": week,
                "subject": subject,
                "generated_at": now.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    if archive_dir is not None:
        from fantasyfootball.archives.evidence import capture

        capture(destination, archive_dir)
    return "ready"


def send(destination):
    destination = Path(destination)
    metadata = json.loads((destination / "delivery.json").read_text())
    if metadata["status"] == "offseason":
        return "offseason"
    if metadata["status"] != "ready":
        raise ValueError("Report is not ready")
    age = datetime.now(timezone.utc) - datetime.fromisoformat(metadata["generated_at"])
    if not 0 <= age.total_seconds() <= 86400:
        raise ValueError("Report is stale or timestamp is in the future")
    ledger = GitHubDeliveryLedger(
        os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]
    )
    mailer = GmailSMTP(os.environ["GMAIL_USERNAME"], os.environ["GMAIL_APP_PASSWORD"])
    return deliver_once(
        ledger,
        mailer,
        os.environ["REPORT_EMAIL_TO"],
        metadata["league_id"],
        metadata["season"],
        metadata["week"],
        metadata["subject"],
        (destination / "report.txt").read_text(encoding="utf-8"),
        (destination / "report.html").read_text(encoding="utf-8"),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "send"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--archive", type=Path, help="Private local evidence directory (prepare only)"
    )
    args = parser.parse_args()
    if args.mode == "send" and args.archive is not None:
        parser.error("--archive is only supported with prepare")
    if args.mode == "prepare":
        status = prepare(
            args.output,
            os.environ["FF_LEAGUE_ID"],
            os.environ["FF_TEAM_NAME"],
            int(os.environ["FF_SEASON"]),
            archive_dir=args.archive,
        )
    else:
        status = send(args.output)
    print("Report status:", status)
    # Actions summaries deliberately omit recipient and player details in this public repo.
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(f"Weekly report: **{status}**.\n")


if __name__ == "__main__":
    main()
