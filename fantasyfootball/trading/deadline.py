"""Sleeper deadline display and conservative email cutoffs."""

import io

import pandas as pd


def trade_window(settings, schedule, season, as_of):
    now = pd.Timestamp(as_of)
    if now.tzinfo is None:
        raise ValueError("Trade deadline checks require timezone-aware time")
    week = int(settings.get("trade_deadline", 0) or 0)
    result = {
        "week": week,
        "review_days": int(settings.get("trade_review_days", 0) or 0),
        "allow_email": not bool(settings.get("disable_trades", 0)),
        "status": "open",
    }
    if not result["allow_email"]:
        result["status"] = "trades_disabled"
    if week == 0:
        result["description"] = "No league trade deadline is configured."
        return result
    if not 1 <= week <= 18:
        raise ValueError("Invalid trade deadline week")
    games = schedule.loc[
        (schedule.season == season)
        & (schedule.week == week)
        & (schedule.game_type == "REG")
    ]
    if games.empty:
        raise ValueError("Deadline week schedule is unavailable")
    times = pd.to_datetime(
        games.gameday + " " + games.gametime, errors="raise"
    ).dt.tz_localize("America/New_York")
    if times.isna().any():
        raise ValueError("Deadline game kickoff is missing")
    last = times.max()
    result.update(
        final_kickoff=last.isoformat(),
        email_cutoff=last.isoformat(),
        description=f"Trade deadline: end of the final Week {week} game, scheduled for {last.strftime('%A, %B %d, %Y')} (kickoff {last.strftime('%I:%M %p')} Eastern). Accept before the game ends; kickoff is not the league deadline.",
    )
    # A final whistle has no fixed timestamp. Stop mail at final kickoff rather
    # than guessing a game duration and risking a post-deadline send.
    if now >= last:
        result.update(allow_email=False, status="trade_deadline_stop")
    return result


def live_trade_window(league_id, season, now, client=None, session=None):
    import requests

    from fantasyfootball.data.sleeper import SleeperClient

    league = (client or SleeperClient()).get(f"league/{league_id}")
    if str(league.get("season")) != str(season):
        raise ValueError("Live trade deadline season does not match")
    response = (session or requests).get(
        "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv",
        timeout=(10, 30),
    )
    response.raise_for_status()
    return trade_window(
        league["settings"], pd.read_csv(io.StringIO(response.text)), season, now
    )
