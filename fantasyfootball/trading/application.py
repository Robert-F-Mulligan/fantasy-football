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


def build_trade_report(args, horizon=None):
    if horizon is not None and not 1 <= horizon <= 18:
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
        weeks = (
            list(range(start, min(17, start + horizon - 1) + 1))
            if horizon is not None
            else list(range(start, 18))
        )
        report["horizon"] = len(weeks)
        config = league_from_dict(read("league-supported-offense.json"))
        raw = pd.read_csv(args.input, dtype={"player_id": str})
        history = prepare_weekly(
            raw.loc[raw.season * 100 + raw.week < args.season * 100 + args.week],
            config.scoring,
        )
        model = FactorModel("weekly").fit(
            history.loc[history.season >= args.season - 2]
        )
        roster = pd.read_csv(
            args.league_dir / "rosters.csv", dtype={"player_id": str, "sleeper_id": str}
        )
        details = json.loads(args.players.read_text(encoding="utf-8-sig"))
        all_owned = roster.copy()
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
        from fantasyfootball.trading.replacements import replacement_pool
        from fantasyfootball.trading.value import (
            RestOfSeasonValue,
            participation_estimates,
        )

        pool = replacement_pool(args, details, all_owned, imported, history)
        combined = pd.concat([roster, pool], ignore_index=True)
        planner = WeeklyLineupPlanner()
        frames = []
        replacement_frames = []
        for week in weeks:
            availability = planner.availability(
                combined,
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
            frame = frame.merge(
                combined[["player_id", "pos"]], on="player_id", validate="one_to_one"
            )
            owned_frame = frame.loc[frame.player_id.isin(roster.player_id)].copy()
            replacement_frame = frame.loc[
                ~frame.player_id.isin(roster.player_id) & frame.status.eq("projected")
            ].copy()
            # Retain distinct real alternatives, never duplicate one waiver player across slots.
            replacement_frame = (
                replacement_frame.sort_values(
                    ["projected_points", "player_id"], ascending=[False, True]
                )
                .groupby("pos", sort=False)
                .head(4)
            )
            replacement_frames.append(replacement_frame)
            frames.append(owned_frame)
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
        replacement_projections = pd.concat(replacement_frames, ignore_index=True)
        replacements = pool.loc[
            pool.player_id.isin(replacement_projections.player_id)
        ].copy()
        team_map = (
            pd.concat(frames + replacement_frames)
            .drop_duplicates("player_id")
            .set_index("player_id")
            .team
        )
        valuation_players = pd.concat([roster, replacements], ignore_index=True)
        valuation_players["team"] = valuation_players.player_id.map(team_map)
        participation = participation_estimates(
            valuation_players, history, schedule, args.season, args.week
        )
        value_model = RestOfSeasonValue(
            roster,
            projections,
            replacements,
            replacement_projections,
            participation,
            slots,
            weeks,
        )
        from fantasyfootball.trading.fairness import OfferFairness, fetch_draft_costs
        from fantasyfootball.trading.market import FairnessAssessment, FantasyCalcMarket

        inventory = getattr(args, "pick_inventory", None)
        rules = getattr(args, "trade_rules", {}).get("keeper_rules") or {}
        costs = (
            fetch_draft_costs(imported["league_id"], args.season, roster)
            if inventory and imported.get("league_id")
            else {}
        )
        offer_fairness = OfferFairness.build(
            roster,
            projections,
            replacements,
            replacement_projections,
            participation,
            season=args.season,
            weeks=weeks,
            inventory=inventory,
            rules=rules,
            keeper_limit=imported.get("waiver_settings", {}).get("max_keepers", 0),
            draft_costs=costs,
            history=history,
        )
        market = FantasyCalcMarket().fetch(imported, roster)
        calculator = TradeCalculator(
            roster,
            projections,
            slots,
            weeks,
            value_model=value_model,
            fairness=FairnessAssessment(market),
            offer_fairness=offer_fairness,
            pick_inventory=inventory,
        )
        opportunities = calculator.opportunities(report["my_roster"])
        if getattr(args, "trade_uncertainty", False):
            from fantasyfootball.trading.uncertainty import (
                TradePredictionRanges,
                replay_trades,
            )

            replay = replay_trades(
                history,
                schedule,
                slots,
                len(weeks),
                teams=imported.get("waiver_settings", {}).get("num_teams", 12),
            )
            uncertainty = TradePredictionRanges.fit(replay, len(weeks))
            uncertainty.evidence.update(
                history_cutoff=int(history.period.max()),
                slots=slots,
                scoring_settings=imported.get("scoring_settings", {}),
                teams=imported.get("waiver_settings", {}).get("num_teams", 12),
            )
            for opportunity in opportunities:
                opportunity["uncertainty"] = uncertainty.assess(
                    calculator,
                    report["my_roster"],
                    opportunity["partner_roster"],
                    opportunity,
                )
            report["uncertainty_validation"] = {
                k: v for k, v in uncertainty.evidence.items() if k != "errors"
            }
            (args.output / "trade-uncertainty.json").write_text(
                json.dumps(uncertainty.evidence, indent=2), encoding="utf-8"
            )
            replay.to_csv(args.output / "trade-uncertainty-replays.csv", index=False)
        report.update(
            status="estimated",
            weeks=weeks,
            history_cutoff=int(model.cutoff),
            opportunities=opportunities,
            roster_strengths=value_model.strengths(roster, report["my_roster"]),
            market_reference={k: v for k, v in market.items() if k != "quotes"},
            fairness_assumptions=offer_fairness.evidence["assumptions"],
            asset_targets=value_model.targets(roster, report["my_roster"]),
            valuation_method="Expected remaining-season lineup points under current-role and historical participation assumptions; waiver alternatives included",
            participation_method="Laplace-smoothed last-eight-team-game scoring-appearance proxy; not a calibrated injury model",
            replacement_assumption="Current unrostered players are weekly streaming alternatives; claim access, competition, FAAB, and drop/reacquisition costs are not modeled",
            scenario_samples=value_model.samples,
            replacement_player_count=len(replacements),
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
        (args.output / "trade-fairness.json").write_text(
            json.dumps(offer_fairness.evidence, indent=2), encoding="utf-8"
        )
        (args.output / "trade-market.json").write_text(
            json.dumps(market, indent=2), encoding="utf-8"
        )
        replacements.to_csv(args.output / "trade-replacements.csv", index=False)
        replacement_projections.to_csv(
            args.output / "trade-replacement-projections.csv", index=False
        )
        participation.to_csv(args.output / "trade-participation.csv", index=False)
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
    from fantasyfootball.trading.value import RestOfSeasonValue

    required = [
        "trade-replacements.csv",
        "trade-replacement-projections.csv",
        "trade-participation.csv",
    ]
    value_model = None
    if report.get("valuation_method"):
        missing = [name for name in required if not (plan / name).exists()]
        if missing:
            raise ValueError(
                "Missing saved ROS valuation evidence: " + ", ".join(missing)
            )
        replacements, alternatives, participation = [
            pd.read_csv(plan / name, dtype={"player_id": str}) for name in required
        ]
        value_model = RestOfSeasonValue(
            roster,
            projections,
            replacements,
            alternatives,
            participation,
            report["slots"],
            report["weeks"],
            samples=report["scenario_samples"],
        )
    from fantasyfootball.trading.market import FairnessAssessment

    market_path = plan / "trade-market.json"
    fairness = (
        FairnessAssessment(json.loads(market_path.read_text(encoding="utf-8")))
        if market_path.exists()
        else None
    )
    from fantasyfootball.trading.fairness import OfferFairness

    estimate_path = plan / "trade-fairness.json"
    offer_fairness = (
        OfferFairness(json.loads(estimate_path.read_text(encoding="utf-8")))
        if estimate_path.exists()
        else None
    )
    from fantasyfootball.trading.uncertainty import TradePredictionRanges

    uncertainty_path = plan / "trade-uncertainty.json"
    uncertainty = (
        TradePredictionRanges(json.loads(uncertainty_path.read_text(encoding="utf-8")))
        if uncertainty_path.exists()
        else None
    )
    if uncertainty is not None and uncertainty.evidence.get(
        "history_cutoff", 0
    ) > report.get("history_cutoff", 0):
        raise ValueError("Uncertainty evidence postdates the saved forecasts")
    return TradeCalculator(
        roster,
        projections,
        report["slots"],
        report["weeks"],
        pick_inventory=picks,
        value_model=value_model,
        fairness=fairness,
        offer_fairness=offer_fairness,
        uncertainty=uncertainty,
    ), report
