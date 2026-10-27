"""Exploratory role-change ablation; production forecasts remain unchanged."""

import argparse
from pathlib import Path

from fantasyfootball.experiments.role_features import RoleFeatures
from fantasyfootball.experiments.usage_experiment import run
from fantasyfootball.forecasting.features import WeeklyFeatures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--league", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(
        args.input,
        args.league,
        args.output,
        builders={
            "baseline": WeeklyFeatures(),
            "momentum": RoleFeatures(),
            "competition": RoleFeatures(competition=True),
        },
        training_season=2021,
        development_seasons=(2022, 2023),
        confirmation_season=2024,
        confirmation_weeks=18,
        extra_checksums=[
            Path(__file__),
            Path(__file__).with_name("role_features.py"),
            Path("docs/ROLE_EXPERIMENT_PROTOCOL.md"),
        ],
        limitations=[
            "Exploratory reuse of 2024, previously evaluated in the opportunity experiment; not an untouched holdout.",
            "Passing numerical gates would require a new prospective validation before promotion.",
            "Observed offensive player-games only; no DNPs, injury labels, or current teammate absences.",
            "Historical corrected data, not as-published Wednesday observations.",
            "Historical same-position teammate shares use observed players, not the full active roster.",
            "Last observed games can cross byes, absences, teams and seasons; no inference of current role certainty.",
            "Same-position close-pair decisions are a proxy, not actual FLEX or roster optimization.",
            "Production unchanged; archived timestamped injury observations are needed for injury testing.",
        ],
    )


if __name__ == "__main__":
    main()
