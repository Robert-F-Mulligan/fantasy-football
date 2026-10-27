import numpy as np
import pandas as pd
import pytest
from test_usage_experiment import history

from fantasyfootball.experiments.role_features import RoleFeatures


def sample():
    data = history()
    data["offense_pct"] = data.week / 10
    return data


@pytest.mark.parametrize("competition", [False, True])
def test_roles_ignore_current_and_future_outcomes(competition):
    data = sample()
    before, columns = RoleFeatures(competition).build(data)
    changed = data.copy()
    changed.loc[
        changed.week >= 5,
        [
            "offense_pct",
            "target_share",
            "rushing_att",
            "receiving_tgt",
            "fantasy_points",
        ],
    ] = 999
    after, _ = RoleFeatures(competition).build(changed)
    pd.testing.assert_frame_equal(
        before.loc[before.week == 5, columns], after.loc[after.week == 5, columns]
    )
    row = before.loc[(before.player_id == "a") & (before.week == 5)].iloc[0]
    assert row.role_last_offense_pct == pytest.approx(0.4)
    assert row.role_change_offense_pct == pytest.approx(0.2)


def test_fixtures_match_historical_features_and_ignore_supplied_usage():
    data = sample()
    full, cols = RoleFeatures(True).build(data)
    fixtures = data.loc[data.week == 5].copy()
    fixtures[["offense_pct", "target_share", "rushing_att", "receiving_tgt"]] = 999
    future, _ = RoleFeatures(True).build(data.loc[data.week < 5], fixtures)
    pd.testing.assert_frame_equal(
        full.loc[full.week == 5, cols].reset_index(drop=True),
        future[cols].reset_index(drop=True),
    )


def test_unknown_competition_is_not_zero():
    data = sample()
    data["rushing_att"] = 0
    data["offense_pct"] = np.nan
    result, _ = RoleFeatures(True).build(data)
    assert result.role_last_position_share_rushing_att.isna().all()
    assert result.role_last_offense_pct.isna().all()
    assert result.loc[result.week < 4, "role_change_target_share"].isna().all()
    with pytest.raises(ValueError, match="Duplicate"):
        RoleFeatures().build(pd.concat([data, data.iloc[:1]]))
    with pytest.raises(ValueError, match="Missing role"):
        RoleFeatures().build(data.drop(columns="offense_pct"))
