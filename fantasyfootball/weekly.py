"""Schedule-aware offensive lineup planning with explicit uncertainty and slot locks."""

import pandas as pd

from .optimization import LineupOptimizer


class WeeklyLineupPlanner:
    def availability(self, roster, player_details, schedule, *, season, week, as_of):
        roster_columns = {
            "sleeper_id",
            "player_id",
            "player_name",
            "pos",
            "starter_slot",
            "is_reserve",
            "is_taxi",
        }
        if not roster_columns.issubset(roster):
            raise ValueError(
                "Refresh the league import: roster must include exact starter slots and reserve flags"
            )
        for flag in ["is_reserve", "is_taxi"]:
            if not roster[flag].isin([True, False]).all():
                raise ValueError("Roster flags must be explicit booleans")
        now = pd.Timestamp(as_of)
        if pd.isna(now) or now.tzinfo is None:
            raise ValueError("as_of must include a timezone")
        if not isinstance(week, int) or not 1 <= week <= 18:
            raise ValueError("Expected regular-season week 1 through 18")
        required = {
            "season",
            "week",
            "game_type",
            "game_id",
            "home_team",
            "away_team",
            "gameday",
            "gametime",
        }
        if not required.issubset(schedule):
            raise ValueError("Schedule lacks required columns")
        games = schedule.loc[
            (pd.to_numeric(schedule.season) == season)
            & (pd.to_numeric(schedule.week) == week)
            & (schedule.game_type == "REG")
        ].copy()
        if games.empty or games.game_id.duplicated().any():
            raise ValueError("Schedule week is missing or has duplicate games")
        # nflverse games.csv uses US Eastern local kickoff times, including DST.
        times = pd.to_datetime(
            games.gameday.astype(str) + " " + games.gametime.astype(str),
            errors="raise",
            format="%Y-%m-%d %H:%M",
        )
        if times.isna().any():
            raise ValueError("Schedule kickoff times are missing")
        games["kickoff"] = times.dt.tz_localize(
            "America/New_York", ambiguous="raise", nonexistent="raise"
        ).dt.tz_convert("UTC")
        teams = {}
        for game in games.itertuples():
            for team, opponent in [
                (game.home_team, game.away_team),
                (game.away_team, game.home_team),
            ]:
                if team in teams:
                    raise ValueError("Team has multiple games in requested week")
                teams[team] = (opponent, game.kickoff, game.game_id)
        season_games = schedule.loc[
            (pd.to_numeric(schedule.season) == season) & (schedule.game_type == "REG")
        ]
        known_teams = set(season_games.home_team) | set(season_games.away_team)
        rows = []
        for row in roster.to_dict("records"):
            details = player_details.get(str(row["sleeper_id"]))
            result = dict(
                row,
                season=season,
                week=week,
                opp=None,
                kickoff=None,
                game_id=None,
                availability="unknown",
                warning="",
                locked_slot="",
            )
            if row.get("pos") in {"K", "DEF"} or (
                details and details.get("position") in {"K", "DEF"}
            ):
                result["availability"] = "unsupported_position"
            elif (
                row.get("pos") not in {"QB", "RB", "WR", "TE"}
                or pd.isna(row.get("player_id"))
                or not details
            ):
                result["warning"] = "Missing canonical ID or current player details"
            else:
                team = details.get("team")
                # Sleeper and nflverse use different Los Angeles Rams abbreviations.
                team = {"LAR": "LA"}.get(team, team)
                result["team"] = team
                if team not in known_teams:
                    result["warning"] = "Missing or unknown current team"
                elif team not in teams:
                    result["availability"] = "no_scheduled_game"
                    result["warning"] = "Bye or incomplete schedule; excluded"
                else:
                    opponent, kickoff, game_id = teams[team]
                    result.update(opp=opponent, kickoff=kickoff, game_id=game_id)
                    slot = row.get("starter_slot")
                    slot = "" if pd.isna(slot) else str(slot)
                    injury = str(details.get("injury_status") or "").casefold()
                    status = str(details.get("status") or "").casefold()
                    if kickoff <= now:
                        result["availability"] = (
                            "locked_starter" if slot else "locked_bench"
                        )
                        result["locked_slot"] = slot
                    elif row.get("is_reserve") or row.get("is_taxi"):
                        result["availability"] = "reserve"
                    elif injury in {
                        "out",
                        "ir",
                        "pup",
                        "suspended",
                        "doubtful",
                    } or status in {"inactive", "injured reserve", "suspended"}:
                        result["availability"] = "unavailable"
                        result["warning"] = f"Status: {status}; injury: {injury}"
                    elif status != "active":
                        result["warning"] = f"Unrecognized status: {status}"
                    else:
                        result["availability"] = "eligible"
                        if injury:
                            result["warning"] = (
                                f"Injury designation: {injury}; recheck before kickoff"
                            )
            rows.append(result)
        return pd.DataFrame(rows)

    def recommend(self, projections, availability, slots):
        if availability.empty or availability.player_id.dropna().duplicated().any():
            raise ValueError("Roster must have unique canonical players")
        unknown = availability.loc[availability.availability == "unknown"]
        if not unknown.empty:
            raise ValueError(
                "Resolve unknown player availability before recommending a lineup"
            )
        candidates = availability.loc[
            availability.availability.isin(["eligible", "locked_starter"])
        ].copy()
        if projections.player_id.duplicated().any():
            raise ValueError("Duplicate player projections")
        board = candidates.merge(
            projections[["player_id", "projected_points"]],
            on="player_id",
            how="left",
            validate="one_to_one",
        )
        if board.projected_points.isna().any():
            raise ValueError("Every eligible or locked player needs a projection")
        fixed = dict(
            zip(
                board.loc[board.locked_slot.ne(""), "locked_slot"],
                board.loc[board.locked_slot.ne(""), "player_id"],
            )
        )
        if len(fixed) != board.locked_slot.ne("").sum():
            raise ValueError("Multiple players occupy the same locked slot")
        return LineupOptimizer().optimize(board, slots, fixed_slots=fixed)


def write_weekly_plan(args):
    """CLI orchestration: preserve audit even when a complete lineup is infeasible."""
    import json
    from hashlib import sha256

    from .application import league_from_dict
    from .features import prepare_weekly
    from .models import FactorModel

    report = json.loads(
        (args.league_dir / "import-report.json").read_text(encoding="utf-8-sig")
    )
    if report["season"] != args.season:
        raise ValueError("Imported league season does not match request")
    if (
        not report["exact_offensive_scoring_supported"]
        and not args.allow_partial_scoring
    ):
        raise ValueError(
            "Scoring is incomplete; inspect import-report.json and explicitly use --allow-partial-scoring for research"
        )
    config = league_from_dict(
        json.loads(
            (args.league_dir / "league-supported-offense.json").read_text(
                encoding="utf-8-sig"
            )
        )
    )
    roster = pd.read_csv(
        args.league_dir / "my_roster.csv", dtype={"player_id": str, "sleeper_id": str}
    )
    for column in ["is_reserve", "is_taxi"]:
        if not roster[column].isin([True, False]).all():
            raise ValueError("Roster flags must be explicit booleans")
    planner = WeeklyLineupPlanner()
    availability = planner.availability(
        roster,
        json.loads(args.players.read_text(encoding="utf-8-sig")),
        pd.read_csv(args.schedule),
        season=args.season,
        week=args.week,
        as_of=args.as_of,
    )
    raw = pd.read_csv(args.input, dtype={"player_id": str})
    history = prepare_weekly(
        raw.loc[(raw.season * 100 + raw.week) < args.season * 100 + args.week],
        config.scoring,
    )
    fixtures = availability.loc[
        availability.availability.isin(["eligible", "locked_starter"]),
        ["player_id", "player_name", "pos", "season", "week", "opp"],
    ]
    model = FactorModel("weekly").fit(history)
    projections = model.predict(fixtures=fixtures)
    slots = json.loads(
        (args.league_dir / "offensive-slots.json").read_text(encoding="utf-8-sig")
    )
    args.output.mkdir(parents=True, exist_ok=False)
    availability.to_csv(args.output / "availability.csv", index=False)
    projections.to_csv(args.output / "projections.csv", index=False)
    audit = {
        "season": args.season,
        "week": args.week,
        "as_of": args.as_of,
        "history_cutoff": int(history.period.max()),
        "dropped_training_features": model.dropped_features,
        "scope": "QB/RB/WR/TE only",
        "unsupported_scoring": report["unsupported_offensive_scoring"],
        "inputs": {
            "history": str(args.input),
            "league": str(args.league_dir),
            "schedule": str(args.schedule),
            "players": str(args.players),
        },
        "notes": [
            "Research projections; no K/DEF recommendations. Recheck injuries and schedule before using.",
            "Caller-supplied snapshots must be current at as_of; historical availability is not reconstructed.",
            "Started players retain their imported slots; their values are preweek predictions, not live remaining points.",
        ],
    }
    audit["input_sha256"] = {
        str(path): sha256(path.read_bytes()).hexdigest()
        for path in [
            args.input,
            args.players,
            args.schedule,
            args.league_dir / "my_roster.csv",
            args.league_dir / "import-report.json",
            args.league_dir / "league-supported-offense.json",
            args.league_dir / "offensive-slots.json",
        ]
    }
    try:
        lineup = planner.recommend(projections, availability, slots)
        lineup.to_csv(args.output / "lineup.csv", index=False)
        audit["status"] = "offensive_lineup_created"
    except ValueError as exc:
        audit["status"] = "blocked"
        audit["reason"] = str(exc)
    (args.output / "plan-report.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


def sync_weekly_context(destination):
    """Fetch one schedule and player-status snapshot; avoid repeated bulk API calls."""
    import json
    from datetime import datetime, timezone
    from hashlib import sha256
    from pathlib import Path

    import requests

    destination = Path(destination)
    if destination.exists():
        raise ValueError("Use a new directory for each weekly context snapshot")
    sources = {
        "games.csv": "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv",
        "players.json": "https://api.sleeper.app/v1/players/nfl",
    }
    payloads = {}
    manifest = {}
    with requests.Session() as session:
        for name, url in sources.items():
            response = session.get(url, timeout=(10, 90))
            response.raise_for_status()
            payloads[name] = response.content
            manifest[name] = {
                "url": url,
                "sha256": sha256(response.content).hexdigest(),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in payloads.items():
        (destination / name).write_bytes(content)
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return destination
