"""Run the frozen snap/high-value opportunity experiment, without production changes."""

import argparse
import json
from pathlib import Path

import pandas as pd

from fantasyfootball.forecasting.features import WeeklyFeatures
from fantasyfootball.experiments.opportunity_features import PBP_COLUMNS, OpportunityFeatures, attach_opportunities
from fantasyfootball.experiments.usage_experiment import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--league", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw_paths = [args.snapshot / "weekly.csv", args.snapshot / "aliases.csv"]
    raw_paths += [args.data / f"snaps-{y}.csv" for y in range(2021, 2025)]
    raw_paths += [args.data / f"play_by_play_{y}.csv.gz" for y in range(2021, 2025)]
    weekly = pd.read_csv(raw_paths[0])
    aliases = pd.read_csv(raw_paths[1], dtype=str)
    snaps = pd.concat([pd.read_csv(p) for p in raw_paths[2:6]], ignore_index=True)
    pbp = pd.concat(
        [pd.read_csv(p, usecols=PBP_COLUMNS) for p in raw_paths[6:]], ignore_index=True
    )
    frame, audit = attach_opportunities(weekly, snaps, aliases, pbp)
    prepared = args.output.with_name(args.output.name + "-input.csv")
    if prepared.exists() or args.output.exists():
        raise ValueError("Use a new output path; do not overwrite an experiment")
    frame.to_csv(prepared, index=False)
    audit_path = prepared.with_suffix(".json")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2), flush=True)
    if any(
        value < 0.95
        for stat in audit["coverage_by_season"].values()
        for value in stat.values()
    ):
        raise ValueError("Raw feature coverage below protocol threshold; inspect audit")
    run(
        prepared,
        args.league,
        args.output,
        builders={
            "baseline": WeeklyFeatures(),
            "snaps": OpportunityFeatures(),
            "opportunities": OpportunityFeatures(high_value=True),
        },
        training_season=2021,
        development_seasons=(2022, 2023),
        confirmation_season=2024,
        confirmation_weeks=18,
        extra_checksums=[
            *raw_paths,
            Path(__file__),
            Path(__file__).with_name("opportunity_features.py"),
            Path("docs/OPPORTUNITY_EXPERIMENT_PROTOCOL.md"),
            audit_path,
        ],
        limitations=[
            "Observed player-games only, excluding DNPs and players without prior observations.",
            "Same-position pair proxy, not actual league rosters or cross-position FLEX decisions.",
            "Corrected snapshots, not as-published historical Wednesday data.",
            "2024 confirmation differs from previous usage holdout but was previously training data.",
            "End-zone targets are inferred from air yards, not charted routes.",
            "History crosses seasons and teams; historical results may not generalize to 2026.",
            "Production unchanged; passing gates requires further contemporary validation.",
        ],
    )


if __name__ == "__main__":
    main()
