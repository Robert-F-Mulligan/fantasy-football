import pandas as pd
import pytest

from fantasyfootball.research.usage import ReceiverUsage


def fixture():
    return pd.DataFrame(
        {
            "game_id": ["g"] * 5,
            "play_id": [1, 2, 3, 4, 5],
            "season": [2026] * 5,
            "week": [1, 1, 2, 2, 3],
            "season_type": ["REG"] * 5,
            "play_type": ["pass"] * 5,
            "two_point_attempt": [0] * 5,
            "posteam": ["A", "A", "B", "B", "A"],
            "receiver_player_id": ["x", "y", "x", None, "x"],
            "receiver_player_name": ["X", "Y", "X", None, "X"],
            "air_yards": [10.0, 30.0, 5.0, None, 100.0],
        }
    )


def test_transfers_cutoff_and_unidentified_passes():
    source = fixture()
    result, audit = ReceiverUsage().summarize(source, season=2026, through_week=2)
    assert len(result) == 3 and audit["unidentified_pass_plays"] == 1
    x = result.loc[result.player_id.eq("x")].set_index("team")
    assert x.loc["A", "target_share"] == 0.5
    assert x.loc["B", "target_share"] == 1
    assert x.loc["A", "air_yard_share"] == 0.25
    assert result.groupby("team").target_share.sum().eq(1).all()
    assert len(source) == 5


def test_missing_air_yards_invalidates_team_share_without_losing_targets():
    source = fixture()
    source.loc[0, "air_yards"] = float("nan")
    result, _ = ReceiverUsage().summarize(source, season=2026, through_week=2)
    assert result.loc[result.team.eq("A"), "air_yard_share"].isna().all()
    assert result.loc[result.team.eq("A"), "target_share"].eq(0.5).all()


def test_nonpositive_denominator_and_duplicate_plays():
    source = fixture()
    source.loc[:1, "air_yards"] = [-5, 5]
    result, _ = ReceiverUsage().summarize(source, season=2026, through_week=2)
    assert result.loc[result.team.eq("A"), "air_yard_share"].isna().all()
    with pytest.raises(ValueError, match="Unique"):
        ReceiverUsage().summarize(
            pd.concat([source, source]), season=2026, through_week=2
        )


def test_empty_period_is_explicit():
    result, audit = ReceiverUsage().summarize(fixture(), season=2025, through_week=2)
    assert result.empty and audit["identified_targets"] == 0


def test_nullified_conversion_and_postseason_plays_are_excluded():
    source = fixture()
    source.loc[0, "play_type"] = "no_play"
    source.loc[1, "two_point_attempt"] = 1
    source.loc[2, "season_type"] = "POST"
    result, audit = ReceiverUsage().summarize(source, season=2026, through_week=2)
    assert result.empty and audit["unidentified_pass_plays"] == 1
