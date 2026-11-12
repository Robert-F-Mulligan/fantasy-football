"""Reproduce horizon-matched trade-interval diagnostics without sending email."""

import argparse
import json
from pathlib import Path

import pandas as pd

from fantasyfootball.drafting.application import league_from_dict
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.trading.uncertainty import TradePredictionRanges, replay_trades


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--schedule", type=Path, required=True)
    parser.add_argument("--league-config", type=Path, required=True)
    parser.add_argument("--slots", type=Path, required=True)
    parser.add_argument(
        "--cutoff", type=int, required=True, help="Exclusive YYYYWW history cutoff"
    )
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--teams", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.horizon <= 17 or args.teams < 2:
        parser.error("Choose horizon 1..17 and at least two teams")
    raw = pd.read_csv(args.input, dtype={"player_id": str})
    league = league_from_dict(
        json.loads(args.league_config.read_text(encoding="utf-8"))
    )
    history = prepare_weekly(
        raw.loc[raw.season * 100 + raw.week < args.cutoff], league.scoring
    )
    slots = json.loads(args.slots.read_text(encoding="utf-8"))
    replay = replay_trades(
        history,
        pd.read_csv(args.schedule),
        slots,
        args.horizon,
        teams=args.teams,
        progress=lambda s: print(s, flush=True),
    )
    model = TradePredictionRanges.fit(replay, args.horizon)
    model.evidence.update(
        history_cutoff=int(history.period.max()), slots=slots, teams=args.teams
    )
    args.output.mkdir(parents=True, exist_ok=True)
    replay.to_csv(args.output / "trade-uncertainty-replays.csv", index=False)
    (args.output / "trade-uncertainty.json").write_text(
        json.dumps(model.evidence, indent=2), encoding="utf-8"
    )
    print(
        json.dumps({k: v for k, v in model.evidence.items() if k != "errors"}, indent=2)
    )


if __name__ == "__main__":
    main()
