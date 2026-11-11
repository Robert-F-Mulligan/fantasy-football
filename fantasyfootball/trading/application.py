"""Build explicitly labeled multi-week trade scenarios from pregame evidence."""

import json
from pathlib import Path

import pandas as pd

from fantasyfootball.drafting.application import league_from_dict
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.forecasting.models import FactorModel
from fantasyfootball.lineups.weekly import WeeklyLineupPlanner
from fantasyfootball.trading.deadline import trade_window
from fantasyfootball.trading.service import TradeCalculator


def build_trade_report(args, horizon=4):
    if not 1 <= horizon <= 18:
        raise ValueError("Horizon must be between 1 and 18 weeks")

    def read(name):
        return json.loads((args.league_dir / name).read_text(encoding="utf-8-sig"))

    imported = read("import-report.json")
    if imported["season"] != args.season:
        raise ValueError("League season does not match request")
    schedule = pd.read_csv(args.schedule)
    games = schedule.loc[
        (schedule.season == args.season) & (schedule.game_type == "REG")
    ]
    this_week = games.loc[games.week == args.week]
    if this_week.empty:
        raise ValueError("Target week is absent from schedule")
    kickoffs = pd.to_datetime(
        this_week.gameday + " " + this_week.gametime
    ).dt.tz_localize("America/New_York")
    start = args.week + int((kickoffs <= pd.Timestamp(args.as_of)).any())
    deadline = imported.get("waiver_settings", {}).get("trade_deadline", 0) or 0
    window = trade_window(
        imported.get("waiver_settings", {}), schedule, args.season, args.as_of
    )
    report = {
        "season": args.season,
        "week": args.week,
        "as_of": args.as_of,
        "my_roster": int(imported["roster_id"]),
        "horizon": horizon,
        "trade_deadline": deadline,
        "deadline": window,
        "opportunities": [],
        "unsupported_scoring": imported.get("unsupported_offensive_scoring", {}),
    }
    if not window["allow_email"] or start > 17:
        report.update(
            status="closed",
            weeks=[],
            reason="Trade window closed for this planning week",
        )
    else:
        weeks = list(range(start, min(17, start + horizon - 1) + 1))
        config = league_from_dict(read("league-supported-offense.json"))
        raw = pd.read_csv(args.input, dtype={"player_id": str})
        history = prepare_weekly(
            raw.loc[raw.season * 100 + raw.week < args.season * 100 + args.week],
            config.scoring,
        )
        model = FactorModel("weekly").fit(history)
        roster = pd.read_csv(
            args.league_dir / "rosters.csv", dtype={"player_id": str, "sleeper_id": str}
        )
        details = json.loads(args.players.read_text(encoding="utf-8-sig"))
        # Keep unresolved offensive records visible as errors, never as empty benches.
        specialist = roster.sleeper_id.map(
            lambda x: details.get(str(x), {}).get("position") in {"K", "DEF"}
        ) | roster.pos.isin(["K", "DEF"])
        roster = roster.loc[~specialist].copy()
        if (
            roster.player_id.isna().any()
            or not roster.pos.isin(["QB", "RB", "WR", "TE"]).all()
        ):
            raise ValueError(
                "Resolve league offensive player IDs before evaluating trades"
            )
        for flag in ["is_reserve", "is_taxi"]:
            if not roster[flag].isin([True, False]).all():
                raise ValueError("Reserve/taxi flags must be explicit booleans")
        report["excluded_reserve_players"] = int(
            (roster.is_reserve | roster.is_taxi).sum()
        )
        roster = roster.loc[~roster.is_reserve & ~roster.is_taxi].copy()
        planner = WeeklyLineupPlanner()
        frames = []
        for week in weeks:
            availability = planner.availability(
                roster,
                details,
                schedule,
                season=args.season,
                week=week,
                as_of=args.as_of,
            )
            fixtures = availability.loc[
                availability.availability.eq("eligible"),
                ["player_id", "player_name", "pos", "season", "week", "opp"],
            ]
            predicted = (
                model.predict(fixtures=fixtures)
                if not fixtures.empty
                else pd.DataFrame(
                    columns=["player_id", "projected_points", "history_games"]
                )
            )
            frame = availability[["player_id", "week", "team", "injury_status"]].merge(
                predicted[["player_id", "projected_points", "history_games"]],
                on="player_id",
                how="left",
            )
            frame["status"] = (
                availability.availability.map(
                    {
                        "eligible": "projected",
                        "no_scheduled_game": "bye",
                        "unavailable": "unavailable",
                    }
                )
                .fillna("unknown")
                .values
            )
            frame.loc[
                frame.status.eq("projected")
                & (frame.projected_points.isna() | frame.history_games.lt(4)),
                "status",
            ] = "unknown"
            frames.append(frame)
        projections = pd.concat(frames, ignore_index=True)
        first = frames[0].set_index("player_id")
        roster["team"] = roster.player_id.map(first.team)
        roster["tradable"] = roster.sleeper_id.map(
            lambda pid: (
                str(details.get(str(pid), {}).get("status", "")).lower() == "active"
                and not details.get(str(pid), {}).get("injury_status")
            )
        )
        slots = read("offensive-slots.json")
        calculator = TradeCalculator(roster, projections, slots, weeks)
        opportunities = calculator.opportunities(report["my_roster"])
        report.update(
            status="estimated",
            weeks=weeks,
            history_cutoff=int(model.cutoff),
            opportunities=opportunities,
            slots=slots,
            unknown_player_weeks=int(projections.status.eq("unknown").sum()),
            unavailable_player_weeks=int(projections.status.eq("unavailable").sum()),
            players={
                row.player_id: {
                    "name": row.player_name,
                    "pos": row.pos,
                    "team": row.team if pd.notna(row.team) else "?",
                }
                for row in roster.itertuples()
            },
        )
        roster.to_csv(args.output / "trade-rosters.csv", index=False)
        projections.to_csv(args.output / "trade-projections.csv", index=False)
    (args.output / "trade-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def load_calculator(plan):
    plan = Path(plan)
    report = json.loads((plan / "trade-report.json").read_text(encoding="utf-8"))
    if report["status"] != "estimated":
        raise ValueError("Trade window is closed")
    roster = pd.read_csv(plan / "trade-rosters.csv", dtype={"player_id": str})
    projections = pd.read_csv(plan / "trade-projections.csv", dtype={"player_id": str})
    pick_path = plan / "trade-picks.json"
    picks = (
        json.loads(pick_path.read_text(encoding="utf-8"))
        if pick_path.exists()
        else None
    )
    return TradeCalculator(
        roster, projections, report["slots"], report["weeks"], pick_inventory=picks
    ), report
