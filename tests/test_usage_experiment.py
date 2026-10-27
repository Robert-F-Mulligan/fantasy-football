import numpy as np
import pandas as pd
import pytest

from fantasyfootball.forecasting.features import STATS, prepare_weekly
from fantasyfootball.experiments.usage_experiment import decision_pairs, paired_interval
from fantasyfootball.experiments.usage_features import UsageFeatures


def history():
    rows = []
    for week in range(1, 9):
        for pid, pos, carries, targets in [
            ("a", "RB", 10, 2),
            ("b", "WR", 0, 8),
            ("c", "QB", 5, 0),
        ]:
            row = {s: 0 for s in STATS}
            row.update(
                player_id=pid,
                player_name=pid,
                pos=pos,
                season=2025,
                week=week,
                team="NE",
                opp="NYJ",
                rushing_att=carries,
                receiving_tgt=targets,
                target_share=targets / 10,
                air_yards_share=targets / 10,
                fumbles_lost=0,
            )
            rows.append(row)
    return prepare_weekly(pd.DataFrame(rows))


def test_usage_is_shifted_and_invariant_to_same_week_and_future_outcomes():
    data = history()
    before, cols = UsageFeatures(trends=True).build(data)
    changed = data.copy()
    changed.loc[
        changed.week >= 5,
        ["target_share", "air_yards_share", "rushing_att", "fantasy_points"],
    ] = 999
    after, _ = UsageFeatures(trends=True).build(changed)
    pd.testing.assert_frame_equal(
        before.loc[before.week <= 5, cols], after.loc[after.week <= 5, cols]
    )
    row = before[(before.player_id == "a") & (before.week == 5)].iloc[0]
    assert row.usage_prior4_carry_share == pytest.approx(10 / 15)
    assert row.usage_prior4_target_share == 0.2
    assert row.usage_change_target_share == 0


def test_fixture_features_match_rolling_training_rows_and_ignore_supplied_usage():
    data = history()
    fixtures = data[data.week == 8].copy()
    all_rows, cols = UsageFeatures(trends=True).build(data)
    fixtures["target_share"] = 999
    fixtures["team"] = "FALSE"
    fixtures["fantasy_points"] = 999
    predicted, _ = UsageFeatures(trends=True).build(data[data.week < 8], fixtures)
    expected = (
        all_rows.loc[all_rows.week == 8]
        .sort_values("player_id")[cols]
        .reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(
        predicted.sort_values("player_id")[cols].reset_index(drop=True), expected
    )


def test_missing_share_is_not_zero_and_zero_carry_denominator_is_missing():
    data = history()
    data["rushing_att"] = 0
    data["target_share"] = np.nan
    result, _ = UsageFeatures().build(data)
    assert result.usage_prior4_carry_share.isna().all()
    assert result.usage_prior4_target_share.isna().all()
    with pytest.raises(ValueError, match="Missing usage"):
        UsageFeatures().build(data.drop(columns="team"))


def test_fixed_pairs_and_week_cluster_interval():
    frame = pd.DataFrame(
        [
            {
                "period": p,
                "pos": "RB",
                "player_id": pid,
                "actual": actual,
                "baseline": b,
                "shares": s,
                "trends": s,
            }
            for p in [202601, 202602]
            for pid, actual, b, s in [("a", 10, 10, 8), ("b", 20, 9, 12)]
        ]
    )
    pairs = decision_pairs(frame)
    assert len(pairs) == 2
    assert pairs.baseline.tolist() == [10, 10]
    assert pairs.shares.tolist() == [0, 0]
    assert paired_interval(pairs, "shares") == [-10, -10]
