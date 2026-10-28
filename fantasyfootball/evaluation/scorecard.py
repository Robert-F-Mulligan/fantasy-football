"""Evaluate sealed weekly forecasts against explicit, finalized outcomes."""

import argparse
import hashlib
import io
import json
from html import escape
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from fantasyfootball.archives.evidence import timestamp, verify
from fantasyfootball.core.domain import ScoringRules
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.lineups.optimization import LineupOptimizer


def scoring_digest(weights):
    normalized = {key: float(value) for key, value in weights.items()}
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


class ArchivedForecast:
    def __init__(self, path):
        self.manifest = verify(path)
        self.sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        with ZipFile(path) as archive:

            def document(name):
                return json.loads(archive.read(name).decode("utf-8-sig"))

            def frame(name):
                return pd.read_csv(
                    io.BytesIO(archive.read(name)),
                    dtype={"player_id": str, "sleeper_id": str},
                )

            self.scoring = document("league/league-supported-offense.json")["scoring"]
            self.slots = document("league/offensive-slots.json")
            self.plan = document("plan/plan-report.json")
            self.roster = frame("plan/availability.csv")
            self.projections = frame("plan/projections.csv")
            self.lineup = frame("plan/lineup.csv")
            self.shadow = (
                frame("plan/shadow-projections.csv")
                if "plan/shadow-projections.csv" in archive.namelist()
                else None
            )
            pointer = document("data/current.json")
            snapshot = pointer["snapshot"].replace("\\", "/")
            self.history = frame("data/" + snapshot + "/weekly.csv")

    def baseline(self):
        period = self.manifest["season"] * 100 + self.manifest["week"]
        history = self.history.loc[
            self.history.season * 100 + self.history.week < period
        ]
        scored = prepare_weekly(history, ScoringRules(self.scoring))
        recent = (
            scored.sort_values(["period", "player_id"]).groupby("player_id").tail(4)
        )
        return (
            recent.groupby("player_id")
            .fantasy_points.agg(baseline_points="mean", baseline_games="size")
            .reset_index()
        )


class FinalOutcomes:
    """Missing players remain unresolved; a DNP needs an explicit evidence record."""

    @staticmethod
    def validate(document, forecast):
        if (document["season"], document["week"]) != (
            forecast.manifest["season"],
            forecast.manifest["week"],
        ):
            raise ValueError("Outcomes season/week do not match forecast")
        if document["scoring_sha256"] != scoring_digest(forecast.scoring):
            raise ValueError("Outcome scoring does not match archived league scoring")
        rows = []
        for row in document["players"]:
            if not row.get("player_id") or row["status"] not in {
                "played",
                "dnp",
                "unresolved",
            }:
                raise ValueError("Invalid outcome identity or status")
            record = dict(row)
            record["player_id"] = str(record["player_id"])
            if row["status"] == "unresolved":
                if row.get("points") is not None:
                    raise ValueError("Unresolved outcomes cannot contain points")
                record["points"] = np.nan
            else:
                if not row.get("source") or not str(row["source"]).strip():
                    raise ValueError("Final outcomes require an evidence source")
                finalized = timestamp(row["finalized_at"])
                if finalized > pd.Timestamp.now(tz="UTC"):
                    raise ValueError("Outcome finalization is in the future")
                points = float(row["points"])
                if not np.isfinite(points) or (row["status"] == "dnp" and points != 0):
                    raise ValueError(
                        "Final points must be finite; confirmed DNP must be zero"
                    )
                record["points"] = points
                roster = forecast.roster.loc[
                    forecast.roster.player_id.eq(record["player_id"])
                ]
                for kickoff in roster.kickoff.dropna():
                    if finalized <= timestamp(kickoff):
                        raise ValueError("Outcome finalized before kickoff")
            rows.append(record)
        result = pd.DataFrame(
            rows, columns=["player_id", "status", "points", "source", "finalized_at"]
        )
        if result.player_id.duplicated().any():
            raise ValueError("Duplicate outcome player IDs")
        return result


def shadow_scores(forecast, board):
    shadow = getattr(forecast, "shadow", None)
    if shadow is None:
        return {"status": "not_recorded"}
    if shadow.player_id.duplicated().any():
        raise ValueError("Duplicate shadow forecast IDs")
    if (
        not shadow.season.eq(forecast.manifest["season"]).all()
        or not shadow.week.eq(forecast.manifest["week"]).all()
    ):
        raise ValueError("Shadow forecast period mismatch")
    sample = board.merge(
        shadow[["player_id", "baseline_points", "candidate_points"]].rename(
            columns={"baseline_points": "recorded_baseline"}
        ),
        on="player_id",
        how="inner",
        validate="one_to_one",
    )
    if not np.allclose(
        sample.recorded_baseline, sample.projected_points, equal_nan=False
    ):
        raise ValueError("Shadow baseline differs from sealed production forecast")
    sample = sample.loc[
        sample.scored
        & sample.status.eq("played")
        & np.isfinite(sample.candidate_points)
    ].copy()
    baseline = (sample.projected_points - sample.points).abs()
    candidate = (sample.candidate_points - sample.points).abs()
    by_position = {}
    if "pos" in sample:
        for position, group in sample.groupby("pos"):
            by_position[position] = {
                "paired_rows": len(group),
                "baseline_absolute_error_sum": float(
                    (group.projected_points - group.points).abs().sum()
                ),
                "candidate_absolute_error_sum": float(
                    (group.candidate_points - group.points).abs().sum()
                ),
            }
    return {
        "by_position": by_position,
        "status": "scored" if len(sample) else "awaiting_outcomes",
        "candidate": "workload_momentum_v1",
        "protocol_window": forecast.manifest["season"] == 2026
        and 9 <= forecast.manifest["week"] <= 17,
        "paired_rows": len(sample),
        "baseline_absolute_error_sum": float(baseline.sum()),
        "candidate_absolute_error_sum": float(candidate.sum()),
        "mae_delta": float((candidate - baseline).mean()) if len(sample) else None,
        "notes": "Played-only, same pregame roster population; weekly descriptive totals, no promotion decision.",
    }


class WeeklyScorecard:
    def evaluate(self, forecast, outcomes=None):
        resolved = (
            FinalOutcomes.validate(outcomes, forecast)
            if outcomes
            else pd.DataFrame(columns=["player_id", "status", "points"])
        )
        board = forecast.roster.loc[
            forecast.roster.pos.isin(["QB", "RB", "WR", "TE"])
        ].copy()
        if board.player_id.isna().any() or board.player_id.duplicated().any():
            raise ValueError("Offensive roster requires unique resolved player IDs")
        projected_columns = ["player_id", "projected_points"] + [
            c
            for c in [
                "prediction_lower",
                "prediction_upper",
                "range_target_coverage",
                "range_status",
            ]
            if c in forecast.projections
        ]
        board = board.merge(
            forecast.projections[projected_columns],
            on="player_id",
            how="left",
            validate="one_to_one",
        )
        board = board.merge(
            forecast.baseline(), on="player_id", how="left", validate="one_to_one"
        )
        board = board.merge(
            pd.DataFrame(forecast.manifest["eligibility"]),
            on="sleeper_id",
            how="left",
            validate="one_to_one",
        )
        board = board.merge(resolved, on="player_id", how="left", validate="one_to_one")
        board["status"] = board.status.fillna("unresolved")
        board["points"] = pd.to_numeric(board.points)
        board["scored"] = (
            board.pregame_evidence.eq(True)
            & board.status.isin(["played", "dnp"])
            & np.isfinite(board.projected_points)
        )
        paired = board.loc[board.scored & np.isfinite(board.baseline_points)]
        metrics = []
        for population, sample in [
            ("all_resolved", paired),
            ("played_only", paired.loc[paired.status.eq("played")]),
        ]:
            for position, group in [("ALL", sample), *list(sample.groupby("pos"))]:
                for model, column in [
                    ("model", "projected_points"),
                    ("recent4", "baseline_points"),
                ]:
                    errors = group[column] - group.points
                    metrics.append(
                        {
                            "population": population,
                            "position": position,
                            "model": model,
                            "n": len(group),
                            "mae": float(errors.abs().mean()) if len(group) else None,
                            "rmse": float(np.sqrt((errors**2).mean()))
                            if len(group)
                            else None,
                            "bias": float(errors.mean()) if len(group) else None,
                        }
                    )
        coverage = []
        if {
            "prediction_lower",
            "prediction_upper",
            "range_status",
            "range_target_coverage",
        }.issubset(board):
            ranges = board.loc[
                board.scored
                & board.status.eq("played")
                & board.range_status.eq("estimated")
            ].copy()
            ranges = ranges.loc[
                np.isfinite(ranges.prediction_lower)
                & np.isfinite(ranges.prediction_upper)
                & ranges.prediction_lower.le(ranges.prediction_upper)
            ]
            for (position, target), group in ranges.groupby(
                ["pos", "range_target_coverage"]
            ):
                coverage.append(
                    {
                        "position": position,
                        "target": float(target),
                        "n": len(group),
                        "covered": int(
                            group.points.between(
                                group.prediction_lower, group.prediction_upper
                            ).sum()
                        ),
                        "coverage": float(
                            group.points.between(
                                group.prediction_lower, group.prediction_upper
                            ).mean()
                        ),
                        "mean_width": float(
                            (group.prediction_upper - group.prediction_lower).mean()
                        ),
                    }
                )
        report = {
            "schema_version": 1,
            "season": forecast.manifest["season"],
            "week": forecast.manifest["week"],
            "captured_at": forecast.manifest["captured_at"],
            "archive_sha256": forecast.sha256,
            "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "unsupported_scoring": getattr(forecast, "plan", {}).get(
                "unsupported_scoring", {}
            ),
            "scoring_sha256": scoring_digest(forecast.scoring),
            "roster_rows": len(board),
            "pregame_rows": int(board.pregame_evidence.eq(True).sum()),
            "scored_rows": int(board.scored.sum()),
            "paired_rows": len(paired),
            "unresolved_rows": int(board.status.eq("unresolved").sum()),
            "confirmed_dnp_rows": int(board.status.eq("dnp").sum()),
            "point_metrics": metrics,
            "shadow": shadow_scores(forecast, board),
            "prediction_ranges": coverage,
            "lineup": self.lineup_regret(forecast, board),
            "limitations": [
                "Offense and archived supported scoring only; K/DEF excluded.",
                "MAE comparisons use identical pregame players with both forecasts and resolved outcomes.",
                "Ranges are conditional on playing; confirmed DNPs are excluded from range coverage.",
                "Recent4 uses only the archived earlier observed games; missing history is not zero.",
                "Final outcome records are explicit caller-supplied evidence, not inferred from missing box scores.",
                "One week cannot establish a predictive edge. No confidence claims or promotion decisions.",
                "Lineup regret evaluates archived recommendations, not confirmed manager lineup submissions.",
                "Evaluate one predeclared snapshot per week; do not cherry-pick reruns.",
            ],
        }
        return report, board

    def lineup_regret(self, forecast, board):
        pool = board.loc[board.availability.isin(["eligible", "locked_starter"])].copy()
        pool["locked_slot"] = pool.locked_slot.fillna("")
        fixed = dict(
            zip(
                pool.loc[pool.locked_slot.ne(""), "locked_slot"],
                pool.loc[pool.locked_slot.ne(""), "player_id"],
            )
        )
        if len(fixed) != int(pool.locked_slot.ne("").sum()):
            return {"status": "unavailable", "reason": "Duplicate kickoff locks"}
        movable = pool.loc[pool.locked_slot.eq("")]
        if movable.empty or not movable.pregame_evidence.eq(True).all():
            return {
                "status": "unavailable",
                "reason": "No complete pregame decision pool; late captures cannot establish lineup regret",
            }
        if not pool.status.isin(["played", "dnp"]).all():
            return {
                "status": "pending",
                "reason": "Resolve every candidate outcome before comparing lineups",
            }
        if pool.baseline_points.isna().any():
            return {
                "status": "unavailable",
                "reason": "Recent4 baseline lacks prior history for a candidate",
            }
        try:
            optimizer = LineupOptimizer()
            selected = forecast.lineup
            if selected.slot.duplicated().any() or set(selected.slot) != set(
                forecast.slots
            ):
                raise ValueError("Archived lineup slots are incomplete or duplicated")
            assignment = dict(zip(selected.slot, selected.player_id))
            if any(assignment.get(slot) != player for slot, player in fixed.items()):
                raise ValueError("Archived lineup violates kickoff locks")
            actual = pool.drop(columns="projected_points").rename(
                columns={"points": "projected_points"}
            )
            chosen = optimizer.optimize(actual, forecast.slots, fixed_slots=assignment)
            best = optimizer.optimize(actual, forecast.slots, fixed_slots=fixed)
            baseline = optimizer.optimize(
                pool.assign(projected_points=pool.baseline_points),
                forecast.slots,
                fixed_slots=fixed,
            )
            baseline_actual = (
                pool.set_index("player_id").loc[baseline.player_id, "points"].sum()
            )
            optimum = float(best.projected_points.sum())
            return {
                "status": "complete",
                "recommended_actual": float(chosen.projected_points.sum()),
                "baseline_actual": float(baseline_actual),
                "hindsight_optimum": optimum,
                "recommended_regret": max(
                    0.0, optimum - float(chosen.projected_points.sum())
                ),
                "baseline_regret": max(0.0, optimum - float(baseline_actual)),
                "fixed_slots": fixed,
                "includes_flex": any(len(p) > 1 for p in forecast.slots.values()),
            }
        except ValueError as exc:
            return {"status": "unavailable", "reason": str(exc)}


def write_scorecard(report, rows, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "scorecard.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    rows.to_csv(output / "player-results.csv", index=False)
    template = {
        "season": report["season"],
        "week": report["week"],
        "scoring_sha256": report["scoring_sha256"],
        "players": [
            {
                "player_id": row.player_id,
                "player_name": row.player_name,
                "status": "unresolved",
                "points": None,
                "source": "",
                "finalized_at": "",
            }
            for row in rows.itertuples()
        ],
    }
    (output / "outcomes-template.json").write_text(
        json.dumps(template, indent=2), encoding="utf-8"
    )
    summary = [m for m in report["point_metrics"] if m["position"] == "ALL"]
    table = (
        pd.DataFrame(summary)
        .fillna("Awaiting evidence")
        .replace(
            {
                "population": {
                    "all_resolved": "All resolved (including confirmed DNP)",
                    "played_only": "Played only",
                },
                "model": {"model": "Production", "recent4": "Recent 4 games"},
            }
        )
        .to_html(
            index=False,
            escape=True,
            na_rep="Awaiting evidence",
            float_format=lambda n: f"{n:.2f}",
        )
    )
    ranges = (
        pd.DataFrame(report["prediction_ranges"]).to_html(index=False, escape=True)
        if report["prediction_ranges"]
        else "<p>No eligible finalized range observations yet.</p>"
    )
    lineup = report["lineup"]
    if lineup["status"] == "complete":
        lineup_html = pd.DataFrame(
            [
                {
                    "Lineup": "Archived recommendation",
                    "Actual points": lineup["recommended_actual"],
                    "Regret": lineup["recommended_regret"],
                },
                {
                    "Lineup": "Recent 4 games",
                    "Actual points": lineup["baseline_actual"],
                    "Regret": lineup["baseline_regret"],
                },
            ]
        ).to_html(index=False, escape=True, float_format=lambda n: f"{n:.2f}")
        lineup_html += f"<p>Best feasible hindsight score: {lineup['hindsight_optimum']:.2f}. Kickoff locks preserved.</p>"
    else:
        lineup_html = "<p>" + escape(lineup["reason"]) + "</p>"
    html = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Weekly accuracy scorecard</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#173047}}table{{border-collapse:collapse;width:100%;margin:20px 0}}th,td{{padding:10px;border-bottom:1px solid #d4dee5;text-align:left}}h1{{font-size:30px}}.note{{padding:16px;background:#edf4f7}}pre{{white-space:pre-wrap}}</style>
<h1>Week {report["week"]} accuracy scorecard  |  {report["season"]}</h1>
<p class="note">{report["pregame_rows"]} pregame forecasts  |  {report["scored_rows"]} resolved scores  |  {report["paired_rows"]} paired comparisons. Missing evidence is not a zero-point result.</p>
<h2>Prediction error</h2><p>MAE is average absolute error; RMSE penalizes large misses. Lower is better. Positive bias means overprediction. Both methods use the same players.</p>{table}<h2>Prediction-range coverage (played only)</h2>{ranges}
<h2>Lineup decisions, including FLEX</h2>{lineup_html}
<h2>Interpretation</h2><ul>{"".join("<li>" + escape(x) + "</li>" for x in report["limitations"])}</ul></html>"""
    (output / "scorecard.html").write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    forecast = ArchivedForecast(args.archive)
    outcomes = (
        json.loads(args.outcomes.read_text(encoding="utf-8-sig"))
        if args.outcomes
        else None
    )
    report, rows = WeeklyScorecard().evaluate(forecast, outcomes)
    report["outcomes_sha256"] = (
        hashlib.sha256(args.outcomes.read_bytes()).hexdigest()
        if args.outcomes
        else None
    )
    write_scorecard(report, rows, args.output)
    print(f"Scorecard written: {report['scored_rows']} resolved pregame observations")


if __name__ == "__main__":
    main()
