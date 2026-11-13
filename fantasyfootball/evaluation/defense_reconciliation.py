"""Compare candidate defense components to explicit Sleeper observations."""

import numpy as np
import pandas as pd

from fantasyfootball.evaluation.defense import COMPONENTS, UNRESOLVED


class DefenseComponentReconciliation:
    """Missing sparse-provider fields are unknown, never assumed to be zero."""

    def compare(self, candidates, records, *, season, through_week):
        if (
            isinstance(season, bool)
            or not isinstance(season, int)
            or season < 1
            or isinstance(through_week, bool)
            or not isinstance(through_week, int)
            or not 1 <= through_week <= 18
        ):
            raise ValueError("Expected integer season and regular-season through-week")
        keys = ["season", "week", "team", "scoring_key"]
        source = candidates.copy()
        source = source.loc[
            source.season.eq(season) & source.week.between(1, through_week)
        ]
        unsupported = set(source.scoring_key) - (set(COMPONENTS) | set(UNRESOLVED))
        if unsupported:
            raise ValueError(
                "Unsupported candidate defense components: "
                + ", ".join(sorted(unsupported))
            )
        if source.duplicated(keys).any():
            raise ValueError("Duplicate candidate defense component")
        observations, seen = [], set()
        for record in records:
            if (
                record.get("season_type") != "regular"
                or record.get("category") != "stat"
            ):
                continue
            if (record.get("player") or {}).get("position") != "DEF":
                continue
            year, week = float(record["season"]), float(record["week"])
            if not all(np.isfinite(v) and v.is_integer() for v in (year, week)):
                raise ValueError("Provider season/week must be finite integers")
            year, week = int(year), int(week)
            if year != season or not 1 <= week <= through_week:
                continue
            team = record["player_id"]
            team = {"LAR": "LA", "WSH": "WAS"}.get(team, team)
            if not isinstance(team, str) or not team.strip():
                raise ValueError("Missing defense team identity")
            identity = (year, week, team)
            if identity in seen:
                raise ValueError("Duplicate Sleeper defense team-week")
            seen.add(identity)
            stats = record.get("stats") or {}
            for key in sorted(source.scoring_key.unique()):
                value = stats.get(key)
                try:
                    value = float(value) if value is not None else float("nan")
                except (TypeError, ValueError):
                    value = float("nan")
                if not np.isfinite(value) or value < 0:
                    value = float("nan")
                observations.append(
                    {
                        "season": year,
                        "week": week,
                        "team": team,
                        "scoring_key": key,
                        "sleeper_count": value,
                    }
                )
        provider = pd.DataFrame(observations, columns=keys + ["sleeper_count"])
        # Only active candidate components have a source comparison. Preserve
        # provider-only team-weeks for those components to expose missing coverage.
        provider = provider.loc[provider.scoring_key.isin(source.scoring_key.unique())]
        detail = source.merge(
            provider, on=keys, how="outer", validate="one_to_one", indicator=True
        )
        detail["difference"] = detail.source_count - detail.sleeper_count
        paired = np.isfinite(detail.source_count) & np.isfinite(detail.sleeper_count)
        detail["status"] = "missing_or_invalid_observation"
        detail.loc[detail._merge.eq("left_only"), "status"] = (
            "missing_provider_team_week"
        )
        detail.loc[detail._merge.eq("right_only"), "status"] = (
            "missing_source_team_week"
        )
        detail.loc[paired, "status"] = "mismatch"
        detail.loc[
            paired & np.isclose(detail.difference, 0, rtol=0, atol=1e-9), "status"
        ] = "matched"
        summaries = []
        for key, group in detail.groupby("scoring_key", sort=True):
            matched = int(group.status.eq("matched").sum())
            mismatch = int(group.status.eq("mismatch").sum())
            summaries.append(
                {
                    "scoring_key": key,
                    "rows": len(group),
                    "paired_rows": matched + mismatch,
                    "matched_rows": matched,
                    "mismatched_rows": mismatch,
                    "unresolved_rows": len(group) - matched - mismatch,
                }
            )
        report = {
            "schema_version": 1,
            "season": season,
            "through_week": through_week,
            "provider_team_weeks": len(seen),
            "components": summaries,
            "ready_for_scoring": False,
            "scope": "Candidate component counts only; not total defense scores, event attribution, or forecast validation",
            "missing_policy": "Absent or invalid Sleeper stat fields remain unknown; sparse records are not zero-filled",
            "limitations": "Provider agreement is not independent play-level verification. Finality and historical scoring settings are not established by this comparison. Unmapped scoring rules remain unresolved.",
        }
        return report, detail.drop(columns="_merge")
