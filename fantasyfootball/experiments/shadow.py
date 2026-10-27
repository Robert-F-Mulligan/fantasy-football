"""Prospective workload-momentum forecasts, isolated from production recommendations."""

import json
from datetime import datetime, timezone
from hashlib import sha256

import pandas as pd
import requests

from fantasyfootball.data.data_sync import NflverseClient
from fantasyfootball.experiments.opportunity_features import normalize_teams
from fantasyfootball.experiments.role_features import RoleFeatures
from fantasyfootball.forecasting.models import FactorModel


def join_snaps(history, snaps, aliases):
    mapping = aliases.loc[aliases.provider.eq("pfr"), ["external_id", "player_id"]]
    if mapping.external_id.duplicated().any():
        raise ValueError("Ambiguous snap IDs")
    snaps = normalize_teams(snaps.loc[snaps.game_type.eq("REG")].copy())
    for column in ["season", "week", "offense_pct"]:
        snaps[column] = pd.to_numeric(snaps[column], errors="raise")
    snaps = snaps.loc[(snaps.season * 100 + snaps.week) <= history.period.max()]
    snaps = snaps.merge(
        mapping,
        left_on="pfr_player_id",
        right_on="external_id",
        how="left",
        validate="many_to_one",
    )
    keys = ["player_id", "season", "week", "team"]
    mapped = snaps.loc[snaps.player_id.notna(), keys + ["offense_pct"]]
    if (
        mapped.duplicated(keys).any()
        or not mapped.offense_pct.dropna().between(0, 1).all()
    ):
        raise ValueError("Invalid snap shares or duplicate games")
    return normalize_teams(history).merge(
        mapped, on=keys, how="left", validate="one_to_one"
    )


def write_shadow(args, history, fixtures, baseline, client=None):
    meta = {
        "status": "unavailable",
        "candidate": "workload_momentum_v1",
        "production_changed": False,
        "protocol": "docs/PROSPECTIVE_MOMENTUM.md",
        "sources": [],
    }
    try:
        client = client or NflverseClient()
        frames = []
        for season in sorted(history.season.unique()):
            frame, source = client.csv("snap_counts", f"snap_counts_{int(season)}.csv")
            frames.append(frame)
            meta["sources"].append(source)
        enriched = join_snaps(
            history,
            pd.concat(frames, ignore_index=True),
            pd.read_csv(args.input.parent / "aliases.csv", dtype=str),
        )
        coverage = (
            enriched.groupby("season")
            .offense_pct.apply(lambda s: float(s.notna().mean()))
            .to_dict()
        )
        meta["snap_coverage_by_season"] = coverage
        if min(coverage.values()) < 0.95:
            raise ValueError("Snap coverage below 95%; candidate not scored")
        model = FactorModel("weekly")
        model.features = RoleFeatures()
        candidate = model.fit(enriched).predict(fixtures=fixtures)
        paired = (
            baseline[
                [
                    "player_id",
                    "player_name",
                    "pos",
                    "season",
                    "week",
                    "opp",
                    "projected_points",
                ]
            ]
            .rename(columns={"projected_points": "baseline_points"})
            .merge(
                candidate[["player_id", "projected_points"]],
                on="player_id",
                validate="one_to_one",
            )
            .rename(columns={"projected_points": "candidate_points"})
        )
        if len(paired) != len(baseline):
            raise ValueError("Shadow prediction populations differ")
        captured = datetime.now(timezone.utc).isoformat()
        paired["generated_at"] = captured
        paired.to_csv(args.output / "shadow-projections.csv", index=False)
        enriched.to_csv(args.output / "shadow-history.csv", index=False)
        meta.update(
            status="recorded",
            generated_at=captured,
            history_cutoff=int(history.period.max()),
            history_sha256=sha256(
                (args.output / "shadow-history.csv").read_bytes()
            ).hexdigest(),
            baseline_sha256=sha256(
                (args.output / "projections.csv").read_bytes()
            ).hexdigest(),
            dropped_features=model.dropped_features,
        )
    except (ValueError, OSError, requests.RequestException) as exc:
        # A research source failure must not stop the established weekly report.
        meta["reason"] = str(exc).split("\n")[0][:240]
    (args.output / "shadow-report.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    return {"status": meta["status"], "candidate": meta["candidate"]}
