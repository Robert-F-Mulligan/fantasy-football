from types import SimpleNamespace

import pandas as pd
import pytest
from test_usage_experiment import history

from fantasyfootball.experiments.shadow import join_snaps, write_shadow


def test_shadow_snap_join_excludes_future_and_requires_unique_keys():
    data = history()
    data["offense_pct"] = 0.5
    snaps = (
        data[["player_id", "season", "week", "team", "offense_pct"]]
        .rename(columns={"player_id": "pfr_player_id"})
        .assign(game_type="REG")
    )
    aliases = pd.DataFrame(
        [
            {"provider": "pfr", "external_id": p, "player_id": p}
            for p in data.player_id.unique()
        ]
    )
    raw = data.drop(columns="offense_pct")
    future = snaps.iloc[:1].assign(week=18, offense_pct=999)
    joined = join_snaps(raw, pd.concat([snaps, future]), aliases)
    assert joined.offense_pct.eq(0.5).all()
    with pytest.raises(ValueError, match="duplicate"):
        join_snaps(raw, pd.concat([snaps, snaps.iloc[:1]]), aliases)


def test_failed_research_source_records_status_without_touching_production(tmp_path):
    class Client:
        def csv(self, *args):
            raise ValueError("missing source")

    (tmp_path / "projections.csv").write_text("production", encoding="utf-8")
    args = SimpleNamespace(output=tmp_path)
    result = write_shadow(args, history(), None, None, Client())
    assert result["status"] == "unavailable"
    assert (tmp_path / "projections.csv").read_text() == "production"
    assert not (tmp_path / "shadow-projections.csv").exists()


def test_paired_shadow_scores_exclude_late_and_unresolved():
    from fantasyfootball.evaluation.scorecard import shadow_scores

    forecast = SimpleNamespace(
        manifest={"season": 2026, "week": 9},
        shadow=pd.DataFrame(
            {
                "player_id": ["a", "b", "c"],
                "season": [2026] * 3,
                "week": [9] * 3,
                "baseline_points": [10.0, 10.0, 10.0],
                "candidate_points": [12.0, 12.0, 12.0],
            }
        ),
    )
    board = pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "projected_points": [10.0, 10.0, 10.0],
            "points": [13.0, 13.0, None],
            "pos": ["RB", "WR", "TE"],
            "scored": [True, False, False],
            "status": ["played", "played", "unresolved"],
        }
    )
    result = shadow_scores(forecast, board)
    assert result["paired_rows"] == 1 and result["mae_delta"] == -2
    assert result["by_position"]["RB"]["paired_rows"] == 1
    assert set(result["by_position"]) == {"RB"}
    assert result["protocol_window"]
    forecast.shadow.loc[0, "baseline_points"] = 99
    with pytest.raises(ValueError, match="baseline differs"):
        shadow_scores(forecast, board)
