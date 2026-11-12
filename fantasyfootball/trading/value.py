"""Roster-relative expected lineup value with shared availability scenarios."""

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


class RestOfSeasonValue:
    def __init__(
        self,
        players,
        projections,
        replacements,
        replacement_projections,
        participation,
        slots,
        weeks,
        samples=128,
        seed=42,
    ):
        if not isinstance(samples, int) or samples < 1:
            raise ValueError("Positive scenario count required")
        if set(players.player_id) & set(replacements.player_id):
            raise ValueError("Replacement pool includes an owned player")
        self.players = pd.concat([players, replacements], ignore_index=True).set_index(
            "player_id"
        )
        if self.players.index.duplicated().any():
            raise ValueError("Valuation needs unique player IDs")
        self.positions = self.players.pos.to_dict()
        self.slots = slots
        self.weeks = weeks
        self.samples = samples
        self.replacement_ids = set(replacements.player_id)
        self.projections = pd.concat(
            [projections, replacement_projections], ignore_index=True
        )
        if self.projections.duplicated(["player_id", "week"]).any():
            raise ValueError("Duplicate valuation player-weeks")
        self.rows = {
            (r.player_id, r.week): (r.status, r.projected_points)
            for r in self.projections.itertuples()
        }
        probabilities = participation.set_index("player_id").probability
        if (
            probabilities.index.duplicated().any()
            or not probabilities.between(0, 1).all()
        ):
            raise ValueError("Invalid participation probabilities")
        if not set(self.players.index).issubset(probabilities.index):
            raise ValueError("Participation estimates missing for valuation players")
        self.probabilities = probabilities.to_dict()
        rng = np.random.default_rng(seed)
        self.draws = {
            (pid, week): rng.random(samples) < float(probabilities.loc[pid])
            for week in weeks
            for pid in sorted(self.players.index)
        }
        self.weekly = lru_cache(maxsize=40000)(self.weekly)

    def weekly(self, ids, week):
        # Claim access is a counterfactual alternative, not guaranteed ownership.
        # Use the same snapshot and availability draws on both sides of a trade.
        selected = []
        for pid in ids:
            row = self.rows.get((pid, week))
            if row is None or row[0] == "unknown":
                return None
            if row[0] == "projected":
                selected.append(pid)
        alternatives = [
            pid
            for pid in self.replacement_ids
            if self.rows.get((pid, week), (None,))[0] == "projected"
        ]
        selected += sorted(alternatives)
        n = len(self.slots)
        if selected:
            points = np.array(
                [self.rows[(pid, week)][1] for pid in selected], dtype=float
            )
            if not np.isfinite(points).all():
                raise ValueError("Valuation points must be finite")
            eligible = np.array(
                [
                    [self.positions[pid] in accepted for pid in selected]
                    for accepted in self.slots.values()
                ]
            )
            present = np.stack([self.draws[(pid, week)] for pid in selected], axis=1)
        else:
            points, eligible, present = (
                np.array([]),
                np.zeros((n, 0), bool),
                np.zeros((self.samples, 0), bool),
            )
        bonus = 2 * (np.abs(points).sum() + 1)
        totals, filled, replacement_points = [], [], []
        contributions = {pos: 0.0 for pos in ["QB", "RB", "WR", "TE"]}
        patterns, counts = np.unique(present, axis=0, return_counts=True)
        for pattern, weight in zip(patterns, counts):
            scores = np.zeros((n, len(selected) + n))
            scores[:, : len(selected)] = np.where(
                eligible & pattern, points + bonus, -np.inf
            )
            _, cols = linear_sum_assignment(-scores)
            chosen = [j for j in cols if j < len(selected)]
            totals.append(sum(points[j] for j in chosen) * weight)
            filled.append(len(chosen) * weight)
            replacement_points.append(
                sum(points[j] for j in chosen if selected[j] in self.replacement_ids)
                * weight
            )
            for j in chosen:
                contributions[self.positions[selected[j]]] += float(points[j] * weight)
        return {
            "points": float(sum(totals) / self.samples),
            "filled": float(sum(filled) / self.samples),
            "slots": n,
            "replacement_points": float(sum(replacement_points) / self.samples),
            "position_points": {p: v / self.samples for p, v in contributions.items()},
        }

    def total(self, ids):
        rows = [self.weekly(tuple(sorted(ids)), week) for week in self.weeks]
        return (
            None
            if any(row is None for row in rows)
            else sum(row["points"] for row in rows)
        )

    def strengths(self, roster, owner):
        rows = []
        all_teams = {}
        for rid, team in roster.groupby("roster_id"):
            ids = set(team.player_id)
            base = self.total(ids)
            if base is None:
                continue
            all_teams[rid] = {}
            for pos in ["QB", "RB", "WR", "TE"]:
                retained = ids - set(team.loc[team.pos.eq(pos), "player_id"])
                without = self.total(retained)
                all_teams[rid][pos] = base - without
        if owner not in all_teams:
            return []
        for pos, value in all_teams[owner].items():
            peers = [scores[pos] for scores in all_teams.values()]
            rows.append(
                {
                    "position": pos,
                    "ros_value_above_replacement": value,
                    "league_median": float(np.median(peers)),
                    "rank": 1 + sum(other > value + 1e-8 for other in peers),
                    "teams_evaluated": len(peers),
                    "league_teams": int(roster.roster_id.nunique()),
                }
            )
        return rows

    def targets(self, roster, owner, limit=5):
        mine = set(roster.loc[roster.roster_id.eq(owner), "player_id"])
        movable = roster.loc[roster.roster_id.eq(owner) & roster.tradable, "player_id"]
        incoming = roster.loc[
            ~roster.roster_id.eq(owner) & roster.tradable, "player_id"
        ]
        base = self.total(mine)
        if base is None:
            return []
        targets = []
        for pid in incoming:
            choices = []
            for displaced in movable:
                value = self.total(mine.difference([displaced]).union([pid]))
                if value is not None:
                    choices.append((value - base, displaced))
            if choices:
                gain, displaced = max(choices, key=lambda row: (row[0], row[1]))
                if round(gain, 1) > 0:
                    targets.append(
                        {
                            "player_id": pid,
                            "marginal_ros_gain": gain,
                            "displaced_player_id": displaced,
                            "acquisition_cost_included": False,
                        }
                    )
        return sorted(
            targets, key=lambda row: (-row["marginal_ros_gain"], row["player_id"])
        )[:limit]


def participation_estimates(players, history, schedule, season, cutoff_week):
    """Laplace-smoothed scoring-appearance rates; not clinical injury probabilities."""
    games = schedule.loc[
        (schedule.season == season)
        & (schedule.week < cutoff_week)
        & (schedule.game_type == "REG")
    ]
    observed = history.loc[(history.season == season) & (history.week < cutoff_week)]
    evidence = []
    for row in players.itertuples():
        past = observed.loc[
            observed.player_id.eq(row.player_id) & observed.team.eq(row.team)
        ]
        team_weeks = sorted(
            set(
                games.loc[
                    games.home_team.eq(row.team) | games.away_team.eq(row.team), "week"
                ]
            )
        )
        if not past.empty:
            team_weeks = [w for w in team_weeks if w >= past.week.min()][-8:]
        else:
            team_weeks = []
        appearances = len(set(past.week) & set(team_weeks))
        evidence.append(
            {
                "player_id": row.player_id,
                "pos": row.pos,
                "appearances": appearances,
                "opportunities": len(team_weeks),
            }
        )
    result = pd.DataFrame(evidence)
    priors = result.groupby("pos")[["appearances", "opportunities"]].sum()
    probabilities, sources = [], []
    for row in result.itertuples():
        if row.opportunities:
            probabilities.append((row.appearances + 1) / (row.opportunities + 2))
            sources.append("last eight observed team opportunities, Laplace smoothing")
        else:
            prior = priors.loc[row.pos]
            if not prior.opportunities:
                raise ValueError("No participation evidence for position " + row.pos)
            probabilities.append((prior.appearances + 1) / (prior.opportunities + 2))
            sources.append("position pooled fallback; no current-team appearances")
    result["probability"], result["source"] = probabilities, sources
    return result
