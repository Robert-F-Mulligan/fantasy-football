import numpy as np
import pandas as pd
import pytest

from fantasyfootball.features import STATS, prepare_weekly
from fantasyfootball.opportunity_features import (
    OpportunityFeatures,
    attach_opportunities,
)
from fantasyfootball.usage_experiment import summarize


def history():
    rows = []
    for week in range(1, 9):
        for pid, pos in [("a", "RB"), ("b", "WR")]:
            rows.append(
                dict.fromkeys(STATS, 0)
                | {
                    "player_id": pid,
                    "player_name": pid,
                    "pos": pos,
                    "season": 2024,
                    "week": week,
                    "team": "LA",
                    "opp": "SF",
                    "fumbles_lost": 0,
                    "offense_pct": 0.75,
                    "goal_line_carries": 2,
                    "end_zone_targets": 1,
                }
            )
    return prepare_weekly(pd.DataFrame(rows))


def test_opportunity_features_do_not_leak_same_week_or_future_outcomes():
    source = history()
    before, cols = OpportunityFeatures(True).build(source)
    changed = source.copy()
    changed.loc[
        changed.week >= 5,
        ["offense_pct", "goal_line_carries", "end_zone_targets", "fantasy_points"],
    ] = 999
    after, _ = OpportunityFeatures(True).build(changed)
    pd.testing.assert_frame_equal(
        before.loc[before.week <= 5, cols], after.loc[after.week <= 5, cols]
    )
    row = before.loc[before.week.eq(5)].iloc[0]
    assert row.opportunity_prior4_offense_pct == 0.75
    assert row.opportunity_prior4_goal_line_carries == 2
    assert row.opportunity_prior12_end_zone_targets == 1


def test_opportunity_fixture_parity_and_missing_values():
    source = history()
    source.loc[source.player_id.eq("b"), "offense_pct"] = np.nan
    before, cols = OpportunityFeatures(True).build(source)
    fixtures = source.loc[source.week.eq(8)].copy()
    fixtures[["offense_pct", "goal_line_carries", "end_zone_targets"]] = 999
    result, _ = OpportunityFeatures(True).build(source.loc[source.week.lt(8)], fixtures)
    pd.testing.assert_frame_equal(
        result.sort_values("player_id")[cols].reset_index(drop=True),
        before.loc[before.week.eq(8)]
        .sort_values("player_id")[cols]
        .reset_index(drop=True),
    )
    assert (
        result.loc[result.player_id.eq("b"), "opportunity_prior4_offense_pct"]
        .isna()
        .all()
    )


def inputs():
    weekly = pd.DataFrame(
        [
            {"player_id": p, "season": 2024, "week": 1, "team": t}
            for p, t in [("a", "LA"), ("b", "LA"), ("c", "NYJ")]
        ]
    )
    aliases = pd.DataFrame(
        [{"provider": "pfr", "external_id": "provider-a", "player_id": "a"}]
    )
    snaps = pd.DataFrame(
        [
            {
                "pfr_player_id": "provider-a",
                "season": 2024,
                "week": 1,
                "team": "LAR",
                "game_type": "REG",
                "offense_pct": 0.5,
            }
        ]
    )
    base = {
        "season": 2024,
        "week": 1,
        "season_type": "REG",
        "game_id": "game1",
        "posteam": "LA",
        "play_type": "run",
        "rush_attempt": 1,
        "pass_attempt": 0,
        "qb_kneel": 0,
        "qb_spike": 0,
        "two_point_attempt": 0,
        "rusher_player_id": "a",
        "receiver_player_id": None,
        "yardline_100": 5,
        "air_yards": np.nan,
    }
    plays = [
        base | {"play_id": 1},
        base | {"play_id": 2, "qb_kneel": 1},
        base | {"play_id": 3, "play_type": "no_play"},
        base | {"play_id": 4, "two_point_attempt": 1},
        base | {"play_id": 5, "yardline_100": 6},
        base
        | {
            "play_id": 6,
            "play_type": "pass",
            "rush_attempt": 0,
            "pass_attempt": 1,
            "rusher_player_id": None,
            "receiver_player_id": "a",
            "air_yards": 5,
        },
        base
        | {
            "play_id": 7,
            "play_type": "pass",
            "rush_attempt": 0,
            "pass_attempt": 1,
            "rusher_player_id": None,
            "receiver_player_id": "b",
        },
    ]
    return weekly, snaps, aliases, pd.DataFrame(plays)


def test_adapter_joins_ids_and_excludes_non_opportunities_without_zero_filling_missing():
    result, audit = attach_opportunities(*inputs())
    result = result.set_index("player_id")
    assert result.loc["a", "offense_pct"] == 0.5
    assert result.loc["a", "goal_line_carries"] == 1
    assert result.loc["a", "end_zone_targets"] == 1
    assert result.loc["b", "goal_line_carries"] == 0
    assert pd.isna(result.loc["b", "end_zone_targets"])  # unknown throw depth
    assert pd.isna(result.loc["c", "goal_line_carries"])  # uncovered team-game
    assert pd.isna(result.loc["b", "offense_pct"])
    assert audit["rows"] == 3


def test_adapter_rejects_ambiguous_ids_and_duplicate_plays():
    weekly, snaps, aliases, pbp = inputs()
    with pytest.raises(ValueError, match="Ambiguous"):
        attach_opportunities(weekly, snaps, pd.concat([aliases, aliases]), pbp)
    with pytest.raises(ValueError, match="Duplicate play"):
        attach_opportunities(weekly, snaps, aliases, pd.concat([pbp, pbp]))


def test_evaluation_accepts_named_candidates_and_keeps_identical_pairs():
    predictions = pd.DataFrame(
        [
            {
                "period": w,
                "pos": "RB",
                "player_id": p,
                "actual": a,
                "baseline": b,
                "snaps": s,
            }
            for w in [202401, 202402]
            for p, a, b, s in [("a", 10, 10, 8), ("b", 20, 9, 12)]
        ]
    )
    report, pairs = summarize(predictions, ("baseline", "snaps"))
    assert pairs.snaps.tolist() == [0, 0]
    assert report["paired_week_bootstrap"]["snaps"]["regret_delta_95_interval"] == [
        -10,
        -10,
    ]
