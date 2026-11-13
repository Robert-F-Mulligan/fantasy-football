"""Audit team-stat coverage for Sleeper defense scoring; never infer full scores."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd

# Candidate source mappings require independent event/league reconciliation.
COMPONENTS = {
    "sack": ("def_sacks",),
    "int": ("def_interceptions",),
    "ff": ("def_fumbles_forced",),
    "tkl_loss": ("def_tackles_for_loss",),
    "safe": ("def_safeties",),
    "blk_kick": ("def_punt_blocks", "def_pat_blocks", "def_fg_blocks"),
    "def_td": ("def_tds",),
    "def_st_td": ("special_teams_tds",),
}
UNRESOLVED = {
    "fum_rec": "Separate defensive recoveries from offensive and special-teams recoveries.",
    "def_st_ff": "Identify forced fumbles on special-teams plays.",
    "def_st_fum_rec": "Identify special-teams fumble recoveries.",
    "def_4_and_stop": "Derive fourth-down stops from eligible plays with penalty/no-play handling.",
}
INDIVIDUAL = {
    "pass_yd",
    "pass_td",
    "pass_int",
    "pass_int_td",
    "pass_2pt",
    "rush_yd",
    "rush_td",
    "rush_2pt",
    "rec",
    "rec_yd",
    "rec_td",
    "rec_2pt",
    "fum",
    "fum_lost",
    "fum_rec_td",
    "st_td",
    "st_ff",
    "st_fum_rec",
}


class DefenseScoringAudit:
    """Report coverage and candidate contributions without zero-filling omissions."""

    def audit(self, raw, settings, *, season, through_week):
        if isinstance(season, bool) or int(season) != season or season < 1:
            raise ValueError("Season must be a positive integer")
        if (
            isinstance(through_week, bool)
            or int(through_week) != through_week
            or not 1 <= through_week <= 18
        ):
            raise ValueError("Through-week must be an integer from 1 to 18")
        keys = ["season", "week", "team", "game_id"]
        if not set(keys + ["season_type"]).issubset(raw):
            raise ValueError(
                "Team stats require season, week, team, game_id and season_type"
            )
        data = raw.copy()
        for key in ["season", "week"]:
            data[key] = pd.to_numeric(data[key], errors="raise")
            if not np.isfinite(data[key]).all() or data[key].mod(1).ne(0).any():
                raise ValueError("Season/week keys must be finite integers")
        data = data.loc[
            data.season.eq(season)
            & data.week.between(1, through_week)
            & data.season_type.eq("REG")
        ].copy()
        if data.empty:
            raise ValueError("No regular-season rows in the requested window")
        if data[["team", "game_id"]].isna().any().any() or any(
            data[k].astype(str).str.strip().eq("").any() for k in ["team", "game_id"]
        ):
            raise ValueError("Team and game IDs cannot be blank")
        if data.duplicated(["season", "week", "team"]).any():
            raise ValueError("Duplicate team-week rows")
        components, rows, ignored = [], [], []
        for key, value in sorted(settings.items()):
            weight = float(value)
            if not np.isfinite(weight):
                raise ValueError("Scoring weights must be finite")
            if not weight:
                continue
            if key in INDIVIDUAL or key.startswith(("fg", "xp")):
                ignored.append(key)
                continue
            columns = COMPONENTS.get(key)
            entry = {
                "scoring_key": key,
                "weight": weight,
                "source_columns": list(columns or ()),
                "rows": len(data),
                "valid_rows": 0,
            }
            if columns is None:
                entry.update(
                    status="requires_attribution",
                    reason=UNRESOLVED.get(
                        key,
                        "Derive fantasy points allowed using Sleeper exclusions; final game score is not a substitute."
                        if key.startswith("pts_allow")
                        else "Unclassified scoring setting; explicit support is required.",
                    ),
                )
            elif not set(columns).issubset(data):
                entry.update(
                    status="missing_columns",
                    reason="Missing: " + ", ".join(sorted(set(columns) - set(data))),
                )
            else:
                values = data[list(columns)].apply(pd.to_numeric, errors="coerce")
                valid = np.isfinite(values).all(axis=1) & values.ge(0).all(axis=1)
                counts = values.sum(axis=1, min_count=len(columns)).where(valid)
                entry.update(
                    status="candidate_mapping" if valid.all() else "invalid_values",
                    valid_rows=int(valid.sum()),
                    reason="Source coverage only; not independently reconciled to Sleeper events or scores.",
                )
                detail = data[keys].copy()
                detail["scoring_key"] = key
                detail["source_count"] = counts
                detail["candidate_component_points"] = counts * weight
                rows.extend(detail.to_dict("records"))
            components.append(entry)
        report = {
            "schema_version": 1,
            "season": int(season),
            "through_week": int(through_week),
            "team_games": len(data),
            "observed_weeks": sorted(int(w) for w in data.week.unique()),
            "ready_for_scoring": False,
            "independent_reconciliation": "not_performed",
            "components": components,
            "ignored_individual_or_kicking_settings": ignored,
            "blocking_components": [
                r["scoring_key"]
                for r in components
                if r["status"] != "candidate_mapping"
            ],
            "limitations": "Coverage audit only. Candidate component contributions are not full defense scores or forecasts. Missing components are not zero; current settings may differ from historical settings.",
        }
        return report, pd.DataFrame(
            rows,
            columns=keys
            + ["scoring_key", "source_count", "candidate_component_points"],
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-stats", type=Path, required=True)
    parser.add_argument(
        "--settings",
        type=Path,
        required=True,
        help="Scoring-settings JSON or import-report.json",
    )
    parser.add_argument(
        "--sleeper-stats",
        type=Path,
        help="Optional saved Sleeper weekly stat records (JSON list)",
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--through-week", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.settings.read_text(encoding="utf-8-sig"))
    report, rows = DefenseScoringAudit().audit(
        pd.read_csv(args.team_stats),
        settings.get("scoring_settings", settings),
        season=args.season,
        through_week=args.through_week,
    )
    report["input_sha256"] = {
        "team_stats": sha256(args.team_stats.read_bytes()).hexdigest(),
        "settings": sha256(args.settings.read_bytes()).hexdigest(),
    }
    comparison = None
    if args.sleeper_stats:
        from fantasyfootball.evaluation.defense_reconciliation import (
            DefenseComponentReconciliation,
        )

        comparison, details = DefenseComponentReconciliation().compare(
            rows,
            json.loads(args.sleeper_stats.read_text(encoding="utf-8-sig")),
            season=args.season,
            through_week=args.through_week,
        )
        report["input_sha256"]["sleeper_stats"] = sha256(
            args.sleeper_stats.read_bytes()
        ).hexdigest()
        comparison["input_sha256"] = report["input_sha256"].copy()
    args.output.mkdir(parents=True, exist_ok=False)
    if comparison is not None:
        (args.output / "reconciliation.json").write_text(
            json.dumps(comparison, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        details.to_csv(args.output / "component-comparisons.csv", index=False)
    (args.output / "coverage.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    rows.to_csv(args.output / "candidate-components.csv", index=False)
    print(
        json.dumps(
            {
                "team_games": report["team_games"],
                "ready_for_scoring": False,
                "blocking_components": report["blocking_components"],
            }
        )
    )


if __name__ == "__main__":
    main()
