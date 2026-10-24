"""Command-line entry point for reproducible offline draft research."""

import argparse
import json
from pathlib import Path
import pandas as pd
from .application import DraftApplication, league_from_dict
from .domain import LeagueSettings
from .drafting import next_snake_pick
from .projections import WeightedHistoryModel, WalkForwardEvaluator


def read_csv(path):
    return pd.read_csv(path, dtype={"player_id": str})


def main(argv=None):
    parser = argparse.ArgumentParser(prog="fantasy-football")
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser(
        "draft", help="Rank projections or historical season totals"
    )
    draft.add_argument("input", type=Path)
    draft.add_argument(
        "--season", type=int, help="Forecast target season from historical data"
    )
    draft.add_argument("--league", type=Path)
    draft.add_argument("--adp", type=Path)
    draft.add_argument(
        "--drafted", nargs="*", default=[], help="Already drafted player IDs"
    )
    draft.add_argument("--pick", type=int, default=1)
    draft.add_argument("--next-pick", type=int)
    draft.add_argument("--output", type=Path, required=True)
    draft.add_argument("--html", type=Path)
    evaluate = commands.add_parser(
        "evaluate", help="Walk-forward historical baseline evaluation"
    )
    evaluate.add_argument("input", type=Path)
    evaluate.add_argument("--output", type=Path, required=True)
    factors = commands.add_parser(
        "evaluate-factors", help="Chronological factor-model evaluation"
    )
    factors.add_argument("input", type=Path)
    factors.add_argument("--horizon", choices=["weekly", "season"], required=True)
    factors.add_argument("--league", type=Path)
    factors.add_argument("--output", type=Path, required=True)
    forecast = commands.add_parser(
        "forecast", help="Fit on weekly history and predict future season or fixtures"
    )
    forecast.add_argument("input", type=Path)
    forecast.add_argument("--horizon", choices=["weekly", "season"], required=True)
    forecast.add_argument("--season", type=int)
    forecast.add_argument("--fixtures", type=Path)
    forecast.add_argument("--league", type=Path)
    forecast.add_argument("--output", type=Path, required=True)
    lineup = commands.add_parser(
        "lineup", help="Optimize projections for your roster and explicit slots"
    )
    lineup.add_argument("input", type=Path)
    lineup.add_argument("--slots", type=Path, required=True)
    lineup.add_argument("--locked", nargs="*", default=[])
    lineup.add_argument("--excluded", nargs="*", default=[])
    lineup.add_argument("--output", type=Path, required=True)
    sync = commands.add_parser(
        "sync-data", help="Download versioned nflverse player data"
    )
    sync.add_argument("--seasons", nargs="+", type=int, required=True)
    sync.add_argument("--roster-season", type=int, required=True)
    sync.add_argument("--minimum-week", type=int)
    sync.add_argument("--output", type=Path, required=True)
    league_import = commands.add_parser(
        "import-sleeper", help="Read-only league settings and roster import"
    )
    league_import.add_argument("league_id")
    league_import.add_argument("--season", type=int, required=True)
    league_import.add_argument("--team", required=True)
    league_import.add_argument("--snapshot", type=Path, required=True)
    league_import.add_argument("--output", type=Path, required=True)
    weekly = commands.add_parser(
        "weekly-plan",
        help="Plan offensive slots using saved schedule and Sleeper snapshots",
    )
    weekly.add_argument("input", type=Path, help="Canonical weekly history CSV")
    weekly.add_argument("--league-dir", type=Path, required=True)
    weekly.add_argument("--schedule", type=Path, required=True)
    weekly.add_argument(
        "--players", type=Path, required=True, help="Sleeper players/nfl JSON snapshot"
    )
    weekly.add_argument("--season", type=int, required=True)
    weekly.add_argument("--week", type=int, required=True)
    weekly.add_argument("--as-of", required=True, help="Timezone-aware timestamp")
    weekly.add_argument("--allow-partial-scoring", action="store_true")
    weekly.add_argument("--output", type=Path, required=True)
    context = commands.add_parser(
        "sync-weekly-context",
        help="Snapshot live NFL schedule and Sleeper player statuses",
    )
    context.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "sync-weekly-context":
            from .weekly import sync_weekly_context

            print(sync_weekly_context(args.output))
            return
        if args.command == "weekly-plan":
            from .weekly import write_weekly_plan

            write_weekly_plan(args)
            return
        if args.command == "import-sleeper":
            from .sleeper import SleeperLeagueImporter, load_registry

            importer = SleeperLeagueImporter()
            bundle = importer.fetch(
                args.league_id, args.season, args.team, load_registry(args.snapshot)
            )
            importer.save(bundle, args.output)
            print(json.dumps(bundle["report"], indent=2))
            return
        if args.command == "sync-data":
            from .data_sync import DataSyncService

            target, report = DataSyncService().sync(
                args.seasons, args.roster_season, args.output, args.minimum_week
            )
            print(
                json.dumps(
                    {"snapshot": str(target), "coverage": report["coverage"]}, indent=2
                )
            )
            return
        if args.command in ("evaluate-factors", "forecast"):
            from .features import prepare_weekly
            from .models import FactorModel

            league = (
                league_from_dict(
                    json.loads(args.league.read_text(encoding="utf-8-sig"))
                )
                if args.league
                else LeagueSettings()
            )
            history = prepare_weekly(read_csv(args.input), league.scoring)
            model = FactorModel(args.horizon)
            if args.command == "evaluate-factors":
                result = model.evaluate(history)
            else:
                model.fit(history)
                result = model.predict(
                    season=args.season,
                    fixtures=read_csv(args.fixtures) if args.fixtures else None,
                )
        elif args.command == "lineup":
            from .optimization import LineupOptimizer

            result = LineupOptimizer().optimize(
                read_csv(args.input),
                json.loads(args.slots.read_text(encoding="utf-8-sig")),
                locked=args.locked,
                excluded=args.excluded,
            )
        elif args.command == "evaluate":
            result = WalkForwardEvaluator(WeightedHistoryModel()).evaluate(
                read_csv(args.input)
            )
        else:
            league = (
                league_from_dict(
                    json.loads(args.league.read_text(encoding="utf-8-sig"))
                )
                if args.league
                else LeagueSettings()
            )
            result = DraftApplication(league).prepare(
                read_csv(args.input),
                season=args.season,
                adp=read_csv(args.adp) if args.adp else None,
                drafted=args.drafted,
                pick=args.pick,
                next_pick=args.next_pick
                if args.next_pick is not None
                else next_snake_pick(args.pick, league.teams),
            )
            if args.html:
                from .visualization import PlotlyVisualizer

                PlotlyVisualizer().write_report(result, args.html)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(args.output, index=False)
        print(f"Wrote {len(result)} rows to {args.output}")
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
