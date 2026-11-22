"""Chronological scoring-appearance/workload ablation; research only.

Missing statistical rows are not injury diagnoses. Historical roster/injury
snapshots are absent; candidates are known players on their last observed team.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from fantasyfootball.core.domain import ScoringRules
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.forecasting.models import FactorModel
from fantasyfootball.experiments.usage_experiment import decision_pairs

FEATURES = ["appearance_rate", "last_appearance", "gap", "points4", "points12",
            "carries4", "targets4", "games", "QB", "RB", "WR", "TE"]
VARIANTS = ("baseline", "availability", "workload", "combined")


def build_panel(history, schedule):
    """Build candidate sets and predictors using strictly earlier observations."""
    rows, omitted = [], 0
    games = schedule.loc[schedule.game_type.eq("REG")].copy()
    for season in sorted(history.season.unique()):
        for week in range(2, 19):
            period = int(season * 100 + week)
            past = history.loc[history.period.lt(period)]
            current = history.loc[history.period.eq(period)]
            fixtures = games.loc[games.season.eq(season) & games.week.eq(week)]
            opponents = {}
            for g in fixtures.itertuples():
                if hasattr(g, "home_score") and pd.isna(g.home_score):
                    continue
                opponents[g.home_team], opponents[g.away_team] = g.away_team, g.home_team
            # Require observed team coverage before interpreting absent rows as zeros.
            covered = set(current.groupby("team").size().loc[lambda s: s.ge(5)].index)
            for pid, previous in past.groupby("player_id", sort=True):
                prior = previous.sort_values("period")
                last = prior.iloc[-1]
                if last.season != season or len(prior) < 4 or last.team not in opponents:
                    continue
                if last.team not in covered:
                    omitted += 1
                    continue
                scheduled = games.loc[games.season.eq(season) & games.week.lt(week)
                    & (games.home_team.eq(last.team) | games.away_team.eq(last.team)), "week"]
                stint = prior.loc[prior.season.eq(season) & prior.team.eq(last.team)]
                opportunities = sorted(w for w in scheduled.unique() if w >= stint.week.min())[-8:]
                appeared = set(stint.week)
                gap = sum(w > stint.week.max() for w in opportunities)
                actual = current.loc[current.player_id.eq(pid)]
                # Different-team outcomes are retained for coverage audit, not reclassified as absences.
                if not actual.empty and actual.iloc[0].team != last.team:
                    omitted += 1
                    continue
                record = dict(player_id=pid, player_name=last.player_name, pos=last.pos,
                    team=last.team, opp=opponents[last.team], season=int(season), week=week,
                    period=period, actual=float(actual.fantasy_points.sum()), observed=int(len(actual)>0),
                    appearance_rate=(len(appeared & set(opportunities))+1)/(len(opportunities)+2),
                    last_appearance=int(bool(opportunities) and opportunities[-1] in appeared), gap=gap,
                    points4=float(prior.tail(4).fantasy_points.mean()),
                    points12=float(prior.tail(12).fantasy_points.mean()),
                    carries4=float(prior.tail(4).rushing_att.mean()),
                    targets4=float(prior.tail(4).receiving_tgt.mean()), games=len(prior))
                record.update({pos: int(last.pos == pos) for pos in ["QB", "RB", "WR", "TE"]})
                rows.append(record)
    return pd.DataFrame(rows), {"excluded_team_coverage_or_transfer_rows": omitted}


def blocked_interval(frame, candidate, *, resamples=4000, block=4):
    """Paired moving-block bootstrap within season; whole weekly cohorts stay together."""
    grouped = frame.assign(delta=frame[candidate]-frame.baseline).groupby("period").delta.agg(["sum", "count"])
    if len(grouped) < block * 2:
        return None
    rng = np.random.default_rng(42)
    indices = np.arange(len(grouped))
    chunks = [indices[i:i+block] for i in range(len(indices)-block+1)]
    means = []
    for _ in range(resamples):
        sample = np.concatenate([chunks[i] for i in rng.integers(len(chunks), size=int(np.ceil(len(indices)/block)))])[:len(indices)]
        means.append(grouped["sum"].to_numpy()[sample].sum()/grouped["count"].to_numpy()[sample].sum())
    return [float(v) for v in np.quantile(means,[.025,.975])]


def metrics(predictions):
    result = {}
    for label, frame in [("all", predictions), ("prior_gap", predictions.loc[predictions.gap.gt(0)])]:
        errors = frame[["period"]].copy()
        values = {}
        for variant in VARIANTS:
            errors[variant] = (frame[variant]-frame.actual).abs()
            values[variant] = {"mae": float(errors[variant].mean()),
                "rmse": float(np.sqrt(((frame[variant]-frame.actual)**2).mean()))}
        pairs = decision_pairs(frame, variants=VARIANTS)
        result[label] = {"rows": len(frame), "weeks": int(frame.period.nunique()), "point_metrics": values,
            "mae_delta_intervals": {v: blocked_interval(errors,v) for v in VARIANTS[1:]},
            "mean_decision_regret": {v: float(pairs[v].mean()) for v in VARIANTS} if len(pairs) else {},
            "regret_delta_intervals": {v: blocked_interval(pairs,v) for v in VARIANTS[1:]} if len(pairs) else {},
            "decision_pairs": len(pairs)}
    result["appearance_brier"] = {
        "baseline": float(((predictions.appearance_rate-predictions.observed)**2).mean()),
        "candidate": float(((predictions.learned_probability-predictions.observed)**2).mean())}
    return result


def outcome_diagnostics(predictions):
    """Post-outcome slices explain results; never use them as pregame features."""
    result = {}
    for label, mask in {
        "observed_after_gap": predictions.gap.gt(0) & predictions.observed.eq(1),
        "still_absent_after_gap": predictions.gap.gt(0) & predictions.observed.eq(0),
        "no_prior_gap": predictions.gap.eq(0),
    }.items():
        frame = predictions.loc[mask]
        errors = frame[["period"]].copy()
        row = {"rows": len(frame), "post_outcome_slice": label != "no_prior_gap"}
        for variant in ["baseline", "combined"]:
            error = frame[variant] - frame.actual
            errors[variant] = error.abs()
            row[variant] = {
                "mae": float(error.abs().mean()) if len(frame) else None,
                "bias": float(error.mean()) if len(frame) else None,
            }
        row["combined_mae_delta_interval"] = blocked_interval(errors, "combined")
        result[label] = row
    return result


def run(input_path, schedule_path, league_path, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    settings = json.loads(Path(league_path).read_text(encoding="utf-8-sig"))
    raw = pd.read_csv(input_path)
    history = prepare_weekly(raw.loc[raw.season.between(2022,2025)], ScoringRules(settings["scoring"]))
    if set(history.season.unique()) != {2022,2023,2024,2025}:
        raise ValueError("Protocol requires complete 2022-2025 history")
    if any(set(g.week) != set(range(1,19)) for _,g in history.groupby("season")):
        raise ValueError("Historical seasons need all 18 weeks")
    panel,audit = build_panel(history,pd.read_csv(schedule_path))
    predictions, selected = [], None
    with threadpool_limits(limits=2):
        for period in sorted(panel.loc[panel.season.ge(2024),"period"].unique()):
            if period >= 202500 and selected is None:
                development = pd.concat(predictions,ignore_index=True)
                selected = min(VARIANTS[1:], key=lambda v: ((development[v]-development.actual).abs().mean(),v))
                (output/"selection.json").write_text(json.dumps({"selected":selected,"selection_season":2024,"confirmation_season":2025}),encoding="utf-8")
            train = panel.loc[panel.period.lt(period)]
            test = panel.loc[panel.period.eq(period)].copy()
            historical = history.loc[history.period.lt(period) & history.season.ge(period//100-2)]
            baseline = FactorModel().fit(historical).predict(fixtures=test[["player_id","player_name","pos","season","week","opp"]])
            baseline = baseline.set_index("player_id").projected_points
            classifier = HistGradientBoostingClassifier(max_iter=80,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10,early_stopping=False,random_state=42)
            classifier.fit(train[FEATURES],train.observed)
            observed = train.loc[train.observed.eq(1)]
            regressor = HistGradientBoostingRegressor(max_iter=80,max_leaf_nodes=7,min_samples_leaf=40,l2_regularization=10,early_stopping=False,random_state=42)
            regressor.fit(observed[FEATURES],observed.actual)
            probability = classifier.predict_proba(test[FEATURES])[:,1]
            workload = regressor.predict(test[FEATURES])
            conditional = test.player_id.map(baseline).to_numpy()
            test["baseline"] = conditional*test.appearance_rate
            test["availability"] = conditional*probability
            test["workload"] = workload*test.appearance_rate
            test["combined"] = workload*probability
            test["learned_probability"] = probability
            test["training_cutoff"] = int(train.period.max())
            predictions.append(test)
            print(f"Completed {period}: {len(test)} candidates",flush=True)
    forecasts = pd.concat(predictions,ignore_index=True)
    forecasts.to_csv(output/"predictions.csv",index=False)
    summary = {
        "protocol":"availability_workload_v1", "selected_on_2024":selected,
        "development":metrics(forecasts.loc[forecasts.season.eq(2024)]),
        "confirmation":metrics(forecasts.loc[forecasts.season.eq(2025)]),
        "coverage":audit,"production_changed":False,
        "confirmation_diagnostics": outcome_diagnostics(forecasts.loc[forecasts.season.eq(2025)]),
        "experiment_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "inference":"95% paired four-week moving-block bootstrap; negative deltas favor candidate. Development intervals are exploratory; confirmation inference applies only to the frozen selected arm. Secondary cohorts and metrics are descriptive.",
        "limits":["Scoring appearance is not injury availability; no historical pregame injury reports or inactive lists",
          "Candidate universe uses last-observed team; transfers and sparse team coverage excluded",
          "Missing rows are zero scoring only within covered completed team weeks; source omissions can remain",
          "Synthetic close start/sit pairs are not actual league roster decisions or championship odds",
          "2025 is a chronological holdout but was previously used elsewhere in repository research; not a pristine lockbox",
          "No production promotion from this experiment alone; prospective validation and pregame injury evidence required"],
        "sha256":{str(Path(p).name):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [input_path,schedule_path,league_path]}}
    (output/"summary.json").write_text(json.dumps(summary,indent=2,allow_nan=False),encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--schedule",type=Path,required=True)
    parser.add_argument("--league",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    run(args.input,args.schedule,args.league,args.output)
