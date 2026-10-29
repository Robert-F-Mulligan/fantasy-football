"""Validate supported research against an explicit, local play-by-play snapshot."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

from fantasyfootball.research.matchups import TeamMatchups
from fantasyfootball.research.tendencies import NeutralTendencies
from fantasyfootball.research.usage import ReceiverUsage

COLUMNS = {
    "game_id",
    "play_id",
    "season",
    "week",
    "season_type",
    "posteam",
    "defteam",
    "play_type",
    "two_point_attempt",
    "qb_dropback",
    "rush_attempt",
    "qb_kneel",
    "qb_spike",
    "epa",
    "sack",
    "down",
    "half_seconds_remaining",
    "wp",
    "receiver_player_id",
    "receiver_player_name",
    "air_yards",
}


def validate_snapshot(
    source, *, season, through_week, expected_sha256=None, charts=False
):
    source = Path(source)
    digest = sha256(source.read_bytes()).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Snapshot checksum mismatch")
    data = pd.read_csv(
        source, usecols=lambda column: column in COLUMNS, low_memory=False
    )
    usage, audit = ReceiverUsage().summarize(
        data, season=season, through_week=through_week
    )
    matchups = TeamMatchups().summarize(data, season=season, through_week=through_week)
    tendencies = NeutralTendencies().summarize(
        data, season=season, through_week=through_week
    )
    if usage.empty or matchups.empty or tendencies.empty:
        raise ValueError(
            "Snapshot lacks observations for one or more research workflows"
        )
    if not np.allclose(usage.groupby("team").target_share.sum(), 1):
        raise ValueError("Identified target shares do not sum to one per team")
    if not matchups.observations.le(matchups.eligible_plays).all():
        raise ValueError("Observed metric counts exceed eligible plays")
    if (
        not (tendencies.dropbacks + tendencies.designed_rushes)
        .eq(tendencies.neutral_plays)
        .all()
    ):
        raise ValueError("Neutral play counts do not reconcile")
    if charts:
        from fantasyfootball.reports.visualization import PlotlyVisualizer

        visualizer = PlotlyVisualizer()
        visualizer.receiver_usage(usage).to_json()
        visualizer.neutral_tendencies(tendencies).to_json()
        offense = matchups.loc[matchups.unit.eq("Offense"), "team"].iloc[0]
        defenses = matchups.loc[
            matchups.unit.eq("Defense") & matchups.team.ne(offense), "team"
        ]
        if defenses.empty:
            raise ValueError("Chart validation requires two distinct teams")
        comparison = TeamMatchups().compare(
            matchups, offense=offense, defense=defenses.iloc[0]
        )
        for metric in TeamMatchups.METRICS:
            visualizer.team_matchup(comparison, metric).to_json()
    return {
        "source_name": source.name,
        "sha256": digest,
        "season": season,
        "through_week": through_week,
        "input_rows": len(data),
        "receiver_team_rows": len(usage),
        "receiver_teams": usage.team.nunique(),
        "receiver_audit": audit,
        "unknown_air_yard_shares": int(usage.air_yard_share.isna().sum()),
        "matchup_rows": len(matchups),
        "matchup_teams": matchups.team.nunique(),
        "missing_metric_observations": int(
            (matchups.eligible_plays - matchups.observations).sum()
        ),
        "tendency_teams": len(tendencies),
        "neutral_plays": int(tendencies.neutral_plays.sum()),
        "incomplete_neutral_context": int(tendencies.incomplete_context.sum()),
        "charts_serialized": charts,
        "status": "passed",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int, required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Also build/serialize charts; requires viz extra",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.resolve() == args.source.resolve():
        parser.error("Output must not overwrite the source snapshot")
    result = validate_snapshot(
        args.source,
        season=args.season,
        through_week=args.through_week,
        expected_sha256=args.expected_sha256,
        charts=args.charts,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Research snapshot validation passed:", args.output)


if __name__ == "__main__":
    main()
