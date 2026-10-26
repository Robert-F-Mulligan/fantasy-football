import pandas as pd
from pathlib import Path
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.forecasting.models import FactorModel
from fantasyfootball.core.domain import LeagueSettings
from fantasyfootball.legacy import config

frames = [
    pd.read_csv(p) for p in sorted(Path("data/game-by-game").glob("*_weekly.csv"))
]
data = pd.concat(frames, ignore_index=True)
data = data[data.pos.isin(["QB", "RB", "WR", "TE"])].copy()
weekly = prepare_weekly(data, LeagueSettings.from_legacy(config.sean).scoring)
print(
    "Training/evaluation data",
    len(weekly),
    "rows",
    weekly.season.min(),
    weekly.season.max(),
    flush=True,
)
results = []
for horizon in ["season", "weekly"]:
    result = FactorModel(horizon).evaluate(weekly, holdouts=[2021, 2022, 2023])
    results.append(result)
    print(result.to_string(index=False), flush=True)
pd.concat(results).to_csv("work/factor_evaluation.csv", index=False)
weekly.to_csv("work/model_history.csv", index=False)
