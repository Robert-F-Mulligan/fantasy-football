"""Reproducible rolling-origin usage ablation; does not alter production models."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from fantasyfootball.core.domain import ScoringRules
from fantasyfootball.forecasting.features import WeeklyFeatures, prepare_weekly
from fantasyfootball.forecasting.models import FactorModel
from fantasyfootball.experiments.usage_features import UsageFeatures

VARIANTS = ("baseline", "shares", "trends")
POOL_SIZES = {"QB": 24, "RB": 60, "WR": 72, "TE": 24}


def paired_interval(frame, candidate, reference="baseline", resamples=2000):
    """Resample entire weeks, preserving paired observations and unequal week sizes."""
    grouped = (
        frame.assign(delta=frame[candidate] - frame[reference])
        .groupby("period")
        .delta.agg(["sum", "count"])
    )
    rng = np.random.default_rng(42)
    draws = rng.integers(0, len(grouped), size=(resamples, len(grouped)))
    means = grouped["sum"].to_numpy()[draws].sum(axis=1) / grouped["count"].to_numpy()[
        draws
    ].sum(axis=1)
    return [float(v) for v in np.quantile(means, [0.025, 0.975])]


def decision_pairs(predictions, variants=VARIANTS):
    records = []
    for (period, pos), frame in predictions.groupby(["period", "pos"]):
        pool = frame.sort_values(
            ["baseline", "player_id"], ascending=[False, True]
        ).head(POOL_SIZES[pos])
        rows = pool.to_dict("records")
        for i, a in enumerate(rows):
            for b in rows[i + 1 :]:
                if abs(a["baseline"] - b["baseline"]) > 3:
                    continue
                best = max(a["actual"], b["actual"])
                record = {
                    "period": int(period),
                    "pos": pos,
                    "player_a": a["player_id"],
                    "player_b": b["player_id"],
                    "actual_tie": a["actual"] == b["actual"],
                }
                for variant in variants:
                    chosen = min([a, b], key=lambda r: (-r[variant], r["player_id"]))
                    record[variant] = best - chosen["actual"]
                    record[variant + "_correct"] = chosen["actual"] == best
                records.append(record)
    return pd.DataFrame(records)


def summarize(predictions, variants=VARIANTS):
    metrics = []
    errors = predictions[["period", "pos"]].copy()
    for variant in variants:
        errors[variant] = (predictions[variant] - predictions.actual).abs()
        for pos, data in [("ALL", predictions), *list(predictions.groupby("pos"))]:
            error = data[variant] - data.actual
            metrics.append(
                {
                    "variant": variant,
                    "position": pos,
                    "rows": len(data),
                    "mae": float(error.abs().mean()),
                    "rmse": float(np.sqrt((error**2).mean())),
                }
            )
    pairs = decision_pairs(predictions, variants)
    pair_metrics = []
    for variant in variants:
        untied = pairs.loc[~pairs.actual_tie]
        pair_metrics.append(
            {
                "variant": variant,
                "pairs": len(pairs),
                "untied_pairs": len(untied),
                "mean_regret": float(pairs[variant].mean()),
                "accuracy": float(untied[variant + "_correct"].mean()),
            }
        )
    intervals = {
        v: {
            "mae_delta_95_interval": paired_interval(errors, v),
            "regret_delta_95_interval": paired_interval(pairs, v),
        }
        for v in variants[1:]
    }
    return {
        "point_metrics": metrics,
        "pair_metrics": pair_metrics,
        "paired_week_bootstrap": intervals,
    }, pairs


def run(
    input_path,
    league_path,
    output,
    *,
    builders=None,
    training_season=2024,
    development_seasons=(2025,),
    confirmation_season=2026,
    confirmation_weeks=6,
    extra_checksums=(),
    limitations=None,
):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = pd.read_csv(input_path, dtype={"player_id": str})
    source = source.loc[
        (source.season * 100 + source.week)
        <= confirmation_season * 100 + confirmation_weeks
    ].copy()
    settings = json.loads(Path(league_path).read_text(encoding="utf-8-sig"))
    history = prepare_weekly(source, ScoringRules(settings["scoring"]))
    if set(history.season.unique()) != {
        training_season,
        *development_seasons,
        confirmation_season,
    }:
        raise ValueError("Input seasons do not match the experiment protocol")
    builders = builders or {
        "baseline": WeeklyFeatures(),
        "shares": UsageFeatures(),
        "trends": UsageFeatures(trends=True),
    }
    variants = tuple(builders)
    matrices = {}
    coverage = {}
    for name, builder in builders.items():
        data, columns = builder.build(history)
        data = data.sort_values(["period", "player_id"]).reset_index(drop=True)
        data = data.loc[data.previous_games > 0].copy()
        matrices[name] = (data, columns)
        coverage[name] = {
            p: group[columns].notna().mean().to_dict()
            for p, group in data.groupby("pos")
        }
    reference = matrices["baseline"][0]
    for data, _ in matrices.values():
        if not data[["player_id", "period"]].equals(reference[["player_id", "period"]]):
            raise ValueError("Variant evaluation populations differ")
    periods = sorted(
        reference.loc[reference.season > training_season, "period"].unique()
    )
    if periods != [s * 100 + w for s in development_seasons for w in range(1, 19)] + [
        confirmation_season * 100 + w for w in range(1, confirmation_weeks + 1)
    ]:
        raise ValueError("Missing development or confirmation weeks")
    predictions = []
    folds = []
    selected = None
    development = None
    with threadpool_limits(limits=2):
        for period in periods:
            # Freeze selection before any confirmation metrics are calculated.
            if period == confirmation_season * 100 + 1:
                dev_frame = pd.concat(predictions, ignore_index=True)
                development, dev_pairs = summarize(dev_frame, variants)
                candidates = [
                    m
                    for m in development["point_metrics"]
                    if m["position"] == "ALL" and m["variant"] != "baseline"
                ]
                selected = min(candidates, key=lambda m: (m["mae"], m["variant"]))[
                    "variant"
                ]
                (output / "selection.json").write_text(
                    json.dumps(
                        {
                            "selected": selected,
                            "selection_seasons": list(development_seasons),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                dev_pairs.to_csv(output / "development-pairs.csv", index=False)
            test = reference.loc[reference.period == period]
            result = (
                test[
                    [
                        "player_id",
                        "player_name",
                        "pos",
                        "period",
                        "previous_games",
                        "fantasy_points",
                    ]
                ]
                .rename(columns={"fantasy_points": "actual"})
                .copy()
            )
            for name, (data, columns) in matrices.items():
                train = data.loc[data.period < period]
                current = data.loc[data.period == period]
                retained = FactorModel._training_columns(train, columns)
                estimator = (
                    FactorModel()._estimator()
                )  # Identical production hyperparameters.
                estimator.fit(train[retained], train.fantasy_points)
                result[name] = estimator.predict(current[retained])
                folds.append(
                    {
                        "period": int(period),
                        "variant": name,
                        "train_rows": len(train),
                        "test_rows": len(current),
                        "train_cutoff": int(train.period.max()),
                        "features": retained,
                    }
                )
            predictions.append(result)
            print(
                f"Completed {int(period)} ({len(test)} forecasts per model)", flush=True
            )
    all_predictions = pd.concat(predictions, ignore_index=True)
    confirmation, pairs = summarize(
        all_predictions.loc[all_predictions.period >= confirmation_season * 100 + 1],
        variants,
    )
    all_predictions.to_csv(output / "predictions.csv", index=False)
    pairs.to_csv(output / "confirmation-pairs.csv", index=False)
    base = next(
        m
        for m in confirmation["point_metrics"]
        if m["variant"] == "baseline" and m["position"] == "ALL"
    )
    winner = next(
        m
        for m in confirmation["point_metrics"]
        if m["variant"] == selected and m["position"] == "ALL"
    )
    improvement = (base["mae"] - winner["mae"]) / base["mae"]
    by_pos = {
        (m["variant"], m["position"]): m["mae"] for m in confirmation["point_metrics"]
    }
    regrets = {m["variant"]: m["mean_regret"] for m in confirmation["pair_metrics"]}
    gates = {
        "mae_improvement_at_least_2pct": improvement >= 0.02,
        "paired_mae_interval_below_zero": confirmation["paired_week_bootstrap"][
            selected
        ]["mae_delta_95_interval"][1]
        < 0,
        "pair_regret_not_over_2pct_worse": regrets[selected]
        <= regrets["baseline"] * 1.02,
        "no_position_over_2pct_worse": all(
            by_pos[selected, p] <= by_pos["baseline", p] * 1.02 for p in POOL_SIZES
        ),
    }
    import scipy
    import sklearn

    checksums = {
        str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest()
        for p in [
            *extra_checksums,
            input_path,
            league_path,
            Path(__file__),
            Path(__file__).with_name("usage_features.py"),
            Path(__file__).parents[1] / "forecasting" / "features.py",
            Path(__file__).parents[1] / "forecasting" / "models.py",
        ]
    }
    report = {
        "selected_on_" + "_".join(map(str, development_seasons)): selected,
        "confirmation_mae_relative_improvement": improvement,
        "promotion_gates": gates,
        "passes_promotion_gates": all(gates.values()),
        "production_changed": False,
        "development": development,
        "confirmation": confirmation,
        "coverage": coverage,
        "folds": folds,
        "input_and_code_sha256": checksums,
        "versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
            "scipy": scipy.__version__,
        },
        "excluded_no_prior_game_rows": int(
            (history.season.gt(training_season)).sum() - len(all_predictions)
        ),
        "limitations": limitations
        or [
            "Observed player-games only; no DNP or historical roster reconstruction.",
            "Pair ranking is a proxy, not realized league lineup value or cross-position FLEX evaluation.",
            "Historical stat corrections use this snapshot, not as-published Wednesday snapshots.",
            "Only six confirmation weeks; bootstrap precision is limited.",
            "Usage history crosses seasons and team changes; no snap/route/red-zone/weather features.",
        ],
    }
    (output / "results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "selected": selected,
                "confirmation_improvement": improvement,
                "promotion_gates": gates,
            }
        ),
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--league", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.league, args.output)


if __name__ == "__main__":
    main()
