"""Prospective, frozen-plan trade scoring. No interim performance inference."""

import hashlib
import json
import math
from collections import Counter

import pandas as pd

from fantasyfootball.archives.evidence import timestamp
from fantasyfootball.trading.uncertainty import planned_lineup


def seal_trade_forecasts(calculator, report, history, schedule):
    season, weeks = report["season"], report["weeks"]
    model = calculator.value_model
    result = {
        "protocol": "trade_fixed_plan_v1",
        "season": season,
        "origin_week": report["week"],
        "weeks": weeks,
        "as_of": report["as_of"],
        "forecasts": [],
        "scope": "Current-season fixed-plan scoring only; not future pick prices or observed trade acceptance",
        "baselines": ["zero_gain", "recent_four_same_plan"],
    }
    if model is None:
        return result
    cutoff = season * 100 + report["week"]
    past = history.loc[history.season * 100 + history.week < cutoff]
    recent = past.sort_values(["season", "week"]).groupby("player_id").tail(4)
    stats = recent.groupby("player_id").fantasy_points.agg(["mean", "size"])
    baseline = stats.loc[stats["size"].ge(4), "mean"].to_dict()
    result["history_cutoff"] = (
        int(past.season.mul(100).add(past.week).max()) if len(past) else None
    )
    team_map = model.players.team.to_dict() if "team" in model.players else {}
    games = schedule.loc[schedule.season.eq(season) & schedule.week.isin(weeks)]
    if "game_type" in games:
        games = games.loc[games.game_type.eq("REG")]
    kickoffs = {}
    for game in games.itertuples():
        if not all(
            hasattr(game, k) for k in ["home_team", "away_team", "gameday", "gametime"]
        ):
            continue
        start = (
            pd.Timestamp(str(game.gameday) + " " + str(game.gametime))
            .tz_localize("America/New_York")
            .tz_convert("UTC")
            .isoformat()
        )
        for team in [game.home_team, game.away_team]:
            kickoffs[(team, int(game.week))] = start
    offers = list(report.get("opportunities", [])) + [
        o["trade"]
        for o in report.get("pick_trade_scenarios", {}).get("offers", [])
        if "trade" in o
    ]
    seen = set()
    for offer in offers:
        for owner, outgoing, incoming, drops, side in [
            (
                report["my_roster"],
                offer["give"],
                offer["receive"],
                offer["my_drops"],
                "you",
            ),
            (
                offer["partner_roster"],
                offer["receive"],
                offer["give"],
                offer["partner_drops"],
                "partner",
            ),
        ]:
            ids = set(
                calculator.roster.loc[
                    calculator.roster.roster_id.eq(owner), "player_id"
                ]
            )
            plans = [
                planned_lineup(
                    model.players.reset_index(),
                    model.projections,
                    calculator.slots,
                    choice | model.replacement_ids,
                    weeks,
                    model.probabilities,
                    optional_ids=model.replacement_ids,
                )
                for choice in [ids, ids.difference(outgoing + drops).union(incoming)]
            ]
            if any(p is None for p in plans):
                continue
            before, after = plans
            a, b = Counter(before["selections"]), Counter(after["selections"])
            delta = [
                {
                    "player_id": pid,
                    "week": int(week),
                    "coefficient": b[(pid, week)] - a[(pid, week)],
                    "kickoff": kickoffs.get((team_map.get(pid), week)),
                }
                for pid, week in sorted(a.keys() | b.keys())
                if b[(pid, week)] != a[(pid, week)]
            ]
            if not delta:
                continue
            key = hashlib.sha256(
                json.dumps([owner, delta], sort_keys=True).encode()
            ).hexdigest()
            if key in seen:
                continue
            seen.add(key)
            recent_gain = (
                sum(
                    row["coefficient"]
                    * baseline[row["player_id"]]
                    * model.probabilities[row["player_id"]]
                    for row in delta
                )
                if all(row["player_id"] in baseline for row in delta)
                else None
            )
            interval = offer.get("uncertainty", {}).get(side, {})
            forecast = {
                "forecast_id": key,
                "owner_id": int(owner),
                "delta": delta,
                "model_gain": after["expected"] - before["expected"],
                "zero_gain": 0.0,
                "recent_four_gain": recent_gain,
            }
            if (
                interval.get("status") == "estimated"
                and abs(interval["expected_gain"] - forecast["model_gain"]) < 1e-6
            ):
                forecast["interval"] = {
                    k: interval[k]
                    for k in [
                        "prediction_lower",
                        "prediction_upper",
                        "probability_positive",
                    ]
                }
            result["forecasts"].append(forecast)
    return result


def evaluate_trade_forecasts(document, outcomes, completed_weeks, captured_at):
    """Outcomes map (player_id, week) to finalized points; missing is never zero."""
    if document["protocol"] != "trade_fixed_plan_v1":
        raise ValueError("Unsupported prospective trade protocol")
    if len({f["forecast_id"] for f in document["forecasts"]}) != len(
        document["forecasts"]
    ):
        raise ValueError("Duplicate prospective trade forecast")
    if document.get("history_cutoff") is not None and document[
        "history_cutoff"
    ] >= document["season"] * 100 + min(document["weeks"]):
        raise ValueError("Prospective trade training is not pregame")
    captured = timestamp(captured_at)
    rows = []
    for forecast in document["forecasts"]:
        row = {"forecast_id": forecast["forecast_id"], "owner_id": forecast["owner_id"]}
        delta = forecast["delta"]
        if (
            not delta
            or len({(d["player_id"], d["week"]) for d in delta}) != len(delta)
            or any(
                d["coefficient"] not in {-1, 1} or d["week"] not in document["weeks"]
                for d in delta
            )
        ):
            raise ValueError("Invalid prospective trade exposure")
        if any(
            not d.get("kickoff") or captured >= timestamp(d["kickoff"]) for d in delta
        ):
            row["status"] = "late_or_unverifiable_capture"
        elif not set(document["weeks"]).issubset(completed_weeks):
            row["status"] = "awaiting_full_horizon"
        elif any((d["player_id"], d["week"]) not in outcomes for d in delta):
            row["status"] = "unresolved_outcomes"
        else:
            actual = sum(
                d["coefficient"] * outcomes[(d["player_id"], d["week"])] for d in delta
            )
            if not math.isfinite(actual) or not math.isfinite(forecast["model_gain"]):
                raise ValueError("Nonfinite trade forecast or outcome")
            row.update(
                status="scored",
                actual_gain=actual,
                model_gain=forecast["model_gain"],
                model_absolute_error=abs(forecast["model_gain"] - actual),
                zero_absolute_error=abs(actual),
            )
            recent = forecast.get("recent_four_gain")
            if recent is not None:
                if not math.isfinite(recent):
                    raise ValueError("Invalid recent-form baseline")
                row["recent_four_absolute_error"] = abs(recent - actual)
            interval = forecast.get("interval")
            if interval:
                row["interval_covered"] = (
                    interval["prediction_lower"]
                    <= actual
                    <= interval["prediction_upper"]
                )
                probability = interval.get("probability_positive")
                if probability is not None:
                    if not 0 <= probability <= 1:
                        raise ValueError("Invalid recorded probability")
                    row["brier"] = (probability - int(actual > 0)) ** 2
        rows.append(row)
    scored = [r for r in rows if r["status"] == "scored"]
    paired = [r for r in scored if "recent_four_absolute_error" in r]

    def average(key, sample):
        return sum(r[key] for r in sample) / len(sample) if sample else None

    return {
        "protocol": document["protocol"],
        "season": document["season"],
        "origin_week": document["origin_week"],
        "horizon": len(document["weeks"]),
        "forecast_count": len(rows),
        "scored_count": len(scored),
        "paired_count": len(paired),
        "status": "complete"
        if rows and len(scored) == len(rows)
        else "pending_or_partial",
        "model_mae_paired": average("model_absolute_error", paired),
        "recent_four_mae_paired": average("recent_four_absolute_error", paired),
        "zero_mae_paired": average("zero_absolute_error", paired),
        "interval_coverage": average(
            "interval_covered", [r for r in scored if "interval_covered" in r]
        ),
        "brier": average("brier", [r for r in scored if "brier" in r]),
        "rows": rows,
        "promotion_decision": None,
        "limitations": "Descriptive same-plan comparisons. Offers and horizons overlap; no independent-sample significance or future-price validation. Missing/DNP evidence remains unresolved.",
    }
