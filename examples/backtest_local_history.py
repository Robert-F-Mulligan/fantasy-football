import pandas as pd
from fantasyfootball.data.adapters import WeeklyHistoryAdapter
from fantasyfootball.core.domain import LeagueSettings
from fantasyfootball.legacy import config
from fantasyfootball.forecasting.projections import WalkForwardEvaluator, WeightedHistoryModel

league = LeagueSettings.from_legacy(config.sean)
frames = []
for year in range(2019, 2024):
    data = pd.read_csv(f"data/game-by-game/{year}_weekly.csv")
    data = data[data.pos.isin(["QB", "RB", "WR", "TE"])].copy()
    print(
        year,
        len(data),
        "duplicate weeks",
        data.duplicated(["player_id", "year", "week"]).sum(),
        "missing scoring cells",
        data[list(league.scoring.weights)].isna().sum().sum(),
    )
    frames.append(WeeklyHistoryAdapter(league.scoring).transform(data))
history = pd.concat(frames, ignore_index=True)
history.to_csv("work/local_history.csv", index=False)
result = WalkForwardEvaluator(WeightedHistoryModel()).evaluate(history)
print(result.to_string(index=False))
result.to_csv("work/local_backtest.csv", index=False)
