"""Export unresolved defense discrepancies with reproducible, non-causal clues."""

import json
from collections import Counter

import numpy as np
import pandas as pd

from fantasyfootball.evaluation.defense import COMPONENTS

TEAM_STATS_DOC = "https://nflreadr.nflverse.com/articles/dictionary_team_stats.html"
SLEEPER_ST_DOC = (
    "https://support.sleeper.com/en/articles/3278982-special-teams-scoring-options"
)
KEYS = ["season", "week", "team"]
CONTEXT = (
    "def_fumbles_forced",
    "def_tds",
    "special_teams_tds",
    "fumble_recovery_tds",
    "fumble_recovery_own",
    "fumble_recovery_opp",
    "def_sacks",
    "def_tackles_for_loss",
)
COLUMNS = [
    "case_id",
    "season",
    "week",
    "team",
    "game_id",
    "scoring_key",
    "source_count",
    "sleeper_count",
    "difference",
    "resolution_status",
    "hypothesis",
    "hypothesis_residual",
    "source_context",
    "sleeper_context",
    "evidence_links",
    "required_evidence",
]


def _count(value):
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if np.isfinite(number) and number >= 0 else None


def _team(team):
    return {"LAR": "LA", "WSH": "WAS"}.get(team, team)


class DefenseDiscrepancyTriage:
    """Arithmetic compatibility suggests investigation; it never resolves a case."""

    def triage(self, comparisons, team_stats, records):
        required = KEYS + ["scoring_key", "source_count", "sleeper_count", "status"]
        if not set(required).issubset(comparisons):
            raise ValueError("Missing comparison columns")
        if comparisons.duplicated(KEYS + ["scoring_key"]).any():
            raise ValueError("Duplicate component comparisons")
        if not set(KEYS + ["season_type", "game_id"]).issubset(team_stats):
            raise ValueError("Missing team-stat context columns")
        raw = team_stats.loc[team_stats.season_type.eq("REG")].copy()
        if raw.duplicated(KEYS).any():
            raise ValueError("Duplicate regular-season team context")
        source = {tuple(row[k] for k in KEYS): row for row in raw.to_dict("records")}
        provider = {}
        for record in records:
            if (
                record.get("season_type") != "regular"
                or record.get("category") != "stat"
                or (record.get("player") or {}).get("position") != "DEF"
            ):
                continue
            year, week = float(record["season"]), float(record["week"])
            if not all(np.isfinite(v) and v.is_integer() for v in (year, week)):
                raise ValueError("Provider season/week must be finite integers")
            identity = (int(year), int(week), _team(record["player_id"]))
            if identity in provider:
                raise ValueError("Duplicate provider context")
            provider[identity] = record.get("stats") or {}
        cases = []
        mismatches = comparisons.loc[comparisons.status.eq("mismatch")]
        for row in mismatches.sort_values(KEYS + ["scoring_key"]).to_dict("records"):
            identity = tuple(row[k] for k in KEYS)
            context = source.get(identity, {})
            stats = provider.get(identity, {})
            a, b = _count(row["source_count"]), _count(row["sleeper_count"])
            if a is None or b is None or np.isclose(a, b, rtol=0, atol=1e-9):
                raise ValueError("Mismatch requires unequal finite nonnegative counts")
            if (
                context
                and pd.notna(row.get("game_id"))
                and row.get("game_id") != context["game_id"]
            ):
                raise ValueError("Comparison and source game IDs disagree")
            key, difference = row["scoring_key"], a - b
            hypothesis, residual = "unexplained", None
            evidence = [TEAM_STATS_DOC]
            needed = "Verify official gamebook and provider corrections at play level."
            if key == "ff":
                special = _count(stats.get("def_st_ff"))
                if special is not None and special > 0:
                    residual = difference - special
                    hypothesis = (
                        "special_teams_ff_arithmetic_compatible"
                        if abs(residual) < 1e-9
                        else "special_teams_ff_does_not_explain_difference"
                    )
                evidence.append(SLEEPER_ST_DOC)
                needed = "Identify each forcing player and play phase; confirm source inclusion and Sleeper category."
            elif key == "def_td":
                recovered = _count(context.get("fumble_recovery_tds"))
                if recovered is not None and recovered > 0:
                    residual = difference + recovered
                    hypothesis = (
                        "fumble_recovery_td_arithmetic_compatible"
                        if abs(residual) < 1e-9
                        else "fumble_recovery_td_does_not_explain_difference"
                    )
                needed = "Classify every fumble-recovery touchdown as defense, offense or special teams; establish overlap with def_tds."
            elif key in ("sack", "tkl_loss"):
                needed = "Review sack/TFL credit, shared credit, no-play penalties and official stat corrections."
            source_fields = sorted(set(CONTEXT) | set(COMPONENTS.get(key, ())))
            cases.append(
                {
                    "case_id": f"{int(row['season'])}-W{int(row['week']):02d}-{row['team']}-{key}",
                    **{k: row[k] for k in KEYS},
                    "game_id": context.get("game_id", row.get("game_id")),
                    "scoring_key": key,
                    "source_count": a,
                    "sleeper_count": b,
                    "difference": difference,
                    "resolution_status": "unresolved",
                    "hypothesis": hypothesis,
                    "hypothesis_residual": residual,
                    "source_context": json.dumps(
                        {k: _count(context.get(k)) for k in source_fields},
                        sort_keys=True,
                    ),
                    "sleeper_context": json.dumps(
                        {
                            k: _count(stats.get(k))
                            for k in sorted(
                                {key, "def_st_ff", "def_td", "def_st_td", "fum_rec"}
                            )
                        },
                        sort_keys=True,
                    ),
                    "evidence_links": json.dumps(evidence),
                    "required_evidence": needed,
                }
            )
        report = {
            "schema_version": 1,
            "mismatch_cases": len(cases),
            "resolved_cases": 0,
            "ready_for_scoring": False,
            "components": dict(
                sorted(Counter(c["scoring_key"] for c in cases).items())
            ),
            "hypotheses": dict(sorted(Counter(c["hypothesis"] for c in cases).items())),
            "limitations": "All cases remain unresolved. Arithmetic compatibility is not event attribution. Documentation links describe categories, not evidence of an individual play. Missing context stays null; no scoring correction is applied.",
        }
        return report, pd.DataFrame(cases, columns=COLUMNS)
