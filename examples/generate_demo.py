"""Generate deterministic synthetic examples, not real player projections."""

from pathlib import Path
import json
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
rows = []
for pos, start, drop in [
    ("QB", 380, 9),
    ("RB", 330, 4),
    ("WR", 320, 3.8),
    ("TE", 250, 6),
]:
    for i in range(1, 61):
        rows.append(
            {
                "player_id": f"{pos}{i:02}",
                "player_name": f"Demo {pos} {i:02}",
                "pos": pos,
                "projected_points": round(
                    max(20, start - i * drop + rng.normal(0, 5)), 1
                ),
            }
        )
players = pd.DataFrame(rows)
players["adp"] = (players.projected_points + rng.normal(0, 30, len(players))).rank(
    ascending=False, method="first"
)
players["adp_std"] = (players.adp * 0.15).clip(lower=4).round(1)
players.to_csv("examples/projections.csv", index=False)
Path("examples/league.json").write_text(
    json.dumps(
        {"teams": 12, "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1}, "flex": 1},
        indent=2,
    ),
    encoding="utf-8",
)
history = []
for year in range(2020, 2024):
    for row in rows:
        history.append(
            {
                "player_id": row["player_id"],
                "player_name": row["player_name"],
                "pos": row["pos"],
                "season": year,
                "games": 17,
                "fantasy_points": round(
                    row["projected_points"] * rng.uniform(0.7, 1.1), 1
                ),
            }
        )
pd.DataFrame(history).to_csv("examples/history.csv", index=False)
