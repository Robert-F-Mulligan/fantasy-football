"""Horizon-matched replay uncertainty for forecast-selected weekly lineups.

Aggregate trade errors retain historical game and temporal dependence. These
empirical prediction intervals are not confidence intervals or coverage guarantees.
"""

import math
from collections import Counter

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


def planned_lineup(
    players, projections, slots, ids, weeks, probabilities, *, optional_ids=()
):
    positions = players.set_index("player_id").pos.to_dict()
    rows = projections.set_index(["player_id", "week"])
    total, selections = 0.0, []
    for week in weeks:
        eligible_ids, points = [], []
        for pid in sorted(ids):
            if (pid, week) not in rows.index or rows.loc[
                (pid, week), "status"
            ] == "unknown":
                if pid in optional_ids:
                    continue
                return None
            row = rows.loc[(pid, week)]
            if row.status == "projected":
                value = float(row.projected_points) * probabilities[pid]
                if not math.isfinite(value):
                    return None
                eligible_ids.append(pid)
                points.append(value)
        n = len(slots)
        scores = np.zeros((n, len(points) + n))
        bonus = 2 * (sum(abs(p) for p in points) + 1)
        for i, accepted in enumerate(slots.values()):
            for j, pid in enumerate(eligible_ids):
                scores[i, j] = (
                    points[j] + bonus if positions[pid] in accepted else -np.inf
                )
        _, cols = linear_sum_assignment(-scores)
        for j in cols:
            if j < len(points):
                total += points[j]
                selections.append((eligible_ids[j], week))
    return {"expected": total, "selections": selections}


def exposure(before, after):
    a, b = Counter(before["selections"]), Counter(after["selections"])
    return sum(abs(b[k] - a[k]) for k in a.keys() | b.keys())


class TradePredictionRanges:
    def __init__(self, evidence):
        self.evidence = evidence

    @classmethod
    def fit(cls, replay, horizon, *, min_rows=30, min_origins=3):
        evidence = {
            "version": 1,
            "status": "insufficient_evidence",
            "horizon": horizon,
            "target_coverage": 0.8,
            "probability_available": False,
            "policy": "Weekly starters fixed using forecast expected points, with current waiver alternatives",
            "limitations": "Synthetic one-for-one trades, not observed league transactions. Overlapping replay windows are dependent. Coverage is descriptive, not guaranteed; future lineup adjustments and waiver access are not modeled.",
        }
        if replay.empty:
            return cls(evidence)
        rows = replay.loc[replay.horizon.eq(horizon) & replay.exposure.gt(0)].copy()
        if rows.empty:
            return cls(evidence)
        if not np.isfinite(
            rows[["expected", "actual", "exposure"]].to_numpy(float)
        ).all():
            raise ValueError("Nonfinite replay evidence")
        seasons = sorted(rows.season.unique())
        if len(seasons) < 2:
            return cls(evidence)
        calibration = rows.loc[rows.season < seasons[-1]]
        validation = rows.loc[rows.season == seasons[-1]]
        evidence.update(
            calibration_seasons=[int(s) for s in seasons[:-1]],
            validation_season=int(seasons[-1]),
            calibration_rows=len(calibration),
            validation_rows=len(validation),
            calibration_origins=int(calibration.origin.nunique()),
            validation_origins=int(validation.origin.nunique()),
        )
        if (
            min(len(calibration), len(validation)) < min_rows
            or min(calibration.origin.nunique(), validation.origin.nunique())
            < min_origins
        ):
            return cls(evidence)
        # Scaling is empirically checked on the same horizon, not a sqrt(time) extrapolation.
        errors = (
            (calibration.actual - calibration.expected) / np.sqrt(calibration.exposure)
        ).to_numpy(float)
        width = float(np.quantile(np.abs(errors), 0.8, method="higher"))
        scales = np.sqrt(validation.exposure.to_numpy(float))
        check = (
            validation.actual - validation.expected
        ).abs().to_numpy() <= width * scales
        probability = np.array(
            [np.mean(errors + x / s > 0) for x, s in zip(validation.expected, scales)]
        )
        outcomes = (validation.actual > 0).to_numpy(float)
        positive_check = (validation.expected > 0).to_numpy()
        positive_count = int(positive_check.sum())
        positive_origins = validation.loc[positive_check, "origin"].nunique()
        brier = (
            float(
                np.mean((probability[positive_check] - outcomes[positive_check]) ** 2)
            )
            if positive_count
            else None
        )
        positive = calibration.loc[calibration.expected > 0]
        baseline_probability = (
            float((positive.actual > 0).mean()) if len(positive) else 0.5
        )
        baseline_brier = (
            float(np.mean((baseline_probability - outcomes[positive_check]) ** 2))
            if positive_count
            else None
        )
        reliability = []
        for lo, hi in [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.000001)]:
            mask = (probability >= lo) & (probability < hi) & positive_check
            if mask.any():
                reliability.append(
                    {
                        "predicted": float(probability[mask].mean()),
                        "observed": float(outcomes[mask].mean()),
                        "rows": int(mask.sum()),
                    }
                )
        evidence.update(
            status="estimated",
            scaled_half_width=width,
            errors=errors.tolist(),
            observed_coverage=float(check.mean()),
            brier=brier,
            baseline_brier=baseline_brier,
            reliability=reliability,
            positive_validation_rows=positive_count,
            positive_observed_coverage=float(check[positive_check].mean())
            if positive_count
            else None,
            probability_available=bool(
                positive_count >= min_rows
                and positive_origins >= min_origins
                and brier < baseline_brier
                and float(check[positive_check].mean()) >= 0.8
            ),
            validation_origin_coverage={
                str(k): float(v)
                for k, v in pd.Series(check, index=validation.index)
                .groupby(validation.origin)
                .mean()
                .items()
            },
        )
        return cls(evidence)

    def apply(self, expected, horizon, changed_player_weeks):
        e = self.evidence
        if not math.isfinite(expected) or changed_player_weeks < 0:
            raise ValueError("Invalid trade uncertainty inputs")
        if e["status"] != "estimated" or horizon != e["horizon"]:
            return {
                "status": "unavailable",
                "reason": "Insufficient horizon-matched historical replay evidence",
            }
        if changed_player_weeks == 0:
            return {
                "status": "unchanged_lineups",
                "expected_gain": 0.0,
                "prediction_lower": 0.0,
                "prediction_upper": 0.0,
                "probability_positive": None,
            }
        scale = math.sqrt(changed_player_weeks)
        return {
            "status": "estimated",
            "expected_gain": float(expected),
            "prediction_lower": float(expected - e["scaled_half_width"] * scale),
            "prediction_upper": float(expected + e["scaled_half_width"] * scale),
            "target_coverage": 0.8,
            "observed_coverage": e["observed_coverage"],
            "probability_positive": float(
                np.mean(np.array(e["errors"]) * scale + expected > 0)
            )
            if e["probability_available"] and expected > 0
            else None,
            "probability_status": "empirical_model_estimate"
            if e["probability_available"] and expected > 0
            else "withheld_validation_scope_coverage_or_brier_check",
            "policy": e["policy"],
            "validation_rows": e["validation_rows"],
            "validation_origins": e["validation_origins"],
            "limitations": e["limitations"],
        }

    def assess(self, calculator, my_roster, partner_roster, result):
        if (
            len(result["give"]) != 1
            or len(result["receive"]) != 1
            or result["my_drops"]
            or result["partner_drops"]
            or result["give_picks"]
            or result["receive_picks"]
        ):
            return {
                "status": "unavailable",
                "reason": "Validation covers one-for-one player trades without drops or picks",
            }
        if self.evidence.get("slots", calculator.slots) != calculator.slots:
            return {
                "status": "unavailable",
                "reason": "Validation roster slots do not match",
            }
        if (
            self.evidence.get("teams", calculator.roster.roster_id.nunique())
            != calculator.roster.roster_id.nunique()
        ):
            return {
                "status": "unavailable",
                "reason": "Validation league size does not match",
            }
        model = calculator.value_model
        if model is None:
            return {
                "status": "unavailable",
                "reason": "Replacement and participation evidence required",
            }

        def plan(owner, give, receive):
            ids = set(
                calculator.roster.loc[
                    calculator.roster.roster_id.eq(owner), "player_id"
                ]
            )
            return [
                planned_lineup(
                    model.players.reset_index(),
                    model.projections,
                    calculator.slots,
                    choice | model.replacement_ids,
                    calculator.weeks,
                    model.probabilities,
                    optional_ids=model.replacement_ids,
                )
                for choice in [ids, ids.difference(give).union(receive)]
            ]

        a, b = plan(my_roster, result["give"], result["receive"])
        c, d = plan(partner_roster, result["receive"], result["give"])
        if any(p is None for p in [a, b, c, d]):
            return {
                "status": "unavailable",
                "reason": "Incomplete player-week evidence",
            }
        mine = self.apply(
            b["expected"] - a["expected"], len(calculator.weeks), exposure(a, b)
        )
        partner = self.apply(
            d["expected"] - c["expected"], len(calculator.weeks), exposure(c, d)
        )
        for summary, before, after in [(mine, a, b), (partner, c, d)]:
            summary["plan_before"] = before["selections"]
            summary["plan_after"] = after["selections"]
        return {
            "status": mine["status"],
            "you": mine,
            "partner": partner,
            "reason": mine.get("reason"),
        }


def replay_trades(
    history,
    schedule,
    slots,
    horizon,
    *,
    teams=12,
    model_factory=None,
    progress=None,
    trials=80,
):
    """Chronological frozen-origin forecasts; no future outcomes select starters."""
    from fantasyfootball.forecasting.models import FactorModel
    from fantasyfootball.trading.value import participation_estimates

    required = {
        "player_id",
        "player_name",
        "pos",
        "team",
        "fantasy_points",
        "period",
        "season",
        "week",
    }
    if not required.issubset(history) or not {
        "home_team",
        "away_team",
        "home_score",
        "away_score",
    }.issubset(schedule):
        return pd.DataFrame()
    completed = [
        int(s)
        for s in sorted(history.season.unique())
        if s < history.season.max()
        and (history.loc[history.season.eq(s), "week"].max() >= 17)
    ]
    if len(completed) < 2 or horizon > 11:
        return pd.DataFrame()
    records = []
    for season in completed[-2:]:
        for origin in range(5, min(10, 18 - horizon) + 1, 2):
            train = history.loc[
                (history.period < season * 100 + origin)
                & (history.season >= season - 2)
            ]
            if len(train) < 100:
                continue
            weeks = list(range(origin, origin + horizon))
            games = schedule.loc[
                schedule.season.eq(season)
                & schedule.week.isin(weeks)
                & schedule.game_type.eq("REG")
            ]
            if (
                set(games.week) != set(weeks)
                or games[["home_score", "away_score"]].isna().any().any()
            ):
                continue
            # Missing player outcomes may mean zero only after whole-week source coverage checks.
            observed = history.loc[history.season.eq(season) & history.week.isin(weeks)]
            if any(
                not (set(g.home_team) | set(g.away_team)).issubset(
                    set(observed.loc[observed.week.eq(w), "team"])
                )
                for w, g in games.groupby("week")
            ):
                continue
            current = train.loc[train.season.eq(season)]
            counts = train.groupby("player_id").size()
            universe = current.sort_values("period").drop_duplicates(
                "player_id", keep="last"
            )
            universe = universe.loc[universe.player_id.map(counts).ge(4)].copy()
            if universe.empty:
                continue
            if progress:
                progress(f"Replay {season} week {origin}, horizon {horizon}")
            model = (model_factory or (lambda: FactorModel("weekly")))().fit(train)
            frames = []
            for week in weeks:
                opponents = {}
                for g in games.loc[games.week.eq(week)].itertuples():
                    opponents[g.home_team] = g.away_team
                    opponents[g.away_team] = g.home_team
                fixtures = universe[["player_id", "player_name", "pos"]].copy()
                fixtures["season"], fixtures["week"] = season, week
                fixtures["opp"] = universe.team.map(opponents).values
                active = fixtures.loc[fixtures.opp.notna()]
                prediction = model.predict(fixtures=active)
                frame = fixtures.merge(
                    prediction[["player_id", "projected_points"]],
                    on="player_id",
                    how="left",
                )
                frame["status"] = np.where(frame.opp.isna(), "bye", "projected")
                frames.append(frame)
            predictions = pd.concat(frames, ignore_index=True)
            rates = (
                participation_estimates(universe, train, schedule, season, origin)
                .set_index("player_id")
                .probability.to_dict()
            )
            rankings = predictions.groupby(
                "player_id"
            ).projected_points.mean() * pd.Series(rates)
            rosters = {i: set() for i in range(teams)}
            replacements = set()
            for pos, group in universe.groupby("pos"):
                ordered = sorted(
                    group.player_id, key=lambda p: (-rankings.get(p, -np.inf), p)
                )
                depth = {"QB": 2, "RB": 4, "WR": 5, "TE": 2}[pos]
                for j, pid in enumerate(ordered[: teams * depth]):
                    rnd, slot = divmod(j, teams)
                    rosters[slot if rnd % 2 == 0 else teams - 1 - slot].add(pid)
                replacements.update(ordered[teams * depth : teams * depth + 4])
            actuals = observed.set_index(["player_id", "week"]).fantasy_points.to_dict()

            def value(
                ids,
                universe=universe,
                predictions=predictions,
                replacements=replacements,
                weeks=weeks,
                rates=rates,
            ):
                return planned_lineup(
                    universe, predictions, slots, ids | replacements, weeks, rates
                )

            baseline = {owner: value(ids) for owner, ids in rosters.items()}
            rng = np.random.default_rng(season * 100 + origin)
            for number in range(trials):
                a, b = rng.choice(teams, 2, replace=False)
                if (
                    not rosters[a]
                    or not rosters[b]
                    or baseline[a] is None
                    or baseline[b] is None
                ):
                    continue
                give = sorted(rosters[a])[int(rng.integers(len(rosters[a])))]
                receive = sorted(rosters[b])[int(rng.integers(len(rosters[b])))]
                for owner, outgoing, incoming in [
                    (a, give, receive),
                    (b, receive, give),
                ]:
                    before = baseline[owner]
                    after = value(
                        rosters[owner].difference([outgoing]).union([incoming])
                    )
                    if after is None:
                        continue
                    changed = exposure(before, after)
                    if not changed:
                        continue
                    expected = after["expected"] - before["expected"]
                    actual = sum(
                        actuals.get(key, 0.0) for key in after["selections"]
                    ) - sum(actuals.get(key, 0.0) for key in before["selections"])
                    records.append(
                        {
                            "season": season,
                            "origin": season * 100 + origin,
                            "horizon": horizon,
                            "trade": number,
                            "side": int(owner),
                            "expected": expected,
                            "actual": actual,
                            "exposure": changed,
                        }
                    )
    return pd.DataFrame(records)
