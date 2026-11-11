"""Evaluate a proposed trade against a saved private trade digest."""

import argparse
import json
from pathlib import Path

from fantasyfootball.trading.application import load_calculator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--partner", type=int, required=True)
    parser.add_argument("--give", nargs="+", default=[], help="Canonical player IDs")
    parser.add_argument("--receive", nargs="+", default=[], help="Canonical player IDs")
    parser.add_argument(
        "--give-picks",
        nargs="+",
        default=[],
        help="Pick IDs: year:round:original-roster",
    )
    parser.add_argument("--receive-picks", nargs="+", default=[])
    parser.add_argument("--drop", nargs="*", default=[])
    parser.add_argument("--partner-drop", nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    calculator, report = load_calculator(args.plan)
    result = calculator.evaluate(
        report["my_roster"],
        args.partner,
        args.give,
        args.receive,
        args.drop,
        args.partner_drop,
        give_picks=args.give_picks,
        receive_picks=args.receive_picks,
    )
    result.update(
        as_of=report["as_of"],
        history_cutoff=report["history_cutoff"],
        method="current-role scenario",
    )
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Trade comparison saved privately to the requested output.")


if __name__ == "__main__":
    main()
