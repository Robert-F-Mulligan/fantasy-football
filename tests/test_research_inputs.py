import pandas as pd
import pytest

from fantasyfootball.research.inputs import (
    ResearchWindow,
    normalize_teams,
    require_binary_flags,
)
from fantasyfootball.research.matchups import TeamMatchups
from fantasyfootball.research.tendencies import NeutralTendencies
from fantasyfootball.research.usage import ReceiverUsage


def fixture():
    return pd.DataFrame(
        {
            "game_id": ["a", "b", "c"],
            "play_id": [1, 1, 1],
            "season": [2026] * 3,
            "week": [1, 2, 20],
            "season_type": ["REG", "REG", "POST"],
            "play_type": ["pass"] * 3,
        }
    )


@pytest.mark.parametrize(
    "season,week",
    [(True, 1), (2026.5, 1), (0, 1), (2026, True), (2026, 1.5), (2026, 0), (2026, 19)],
)
def test_invalid_window_rejected(season, week):
    with pytest.raises(ValueError):
        ResearchWindow(season, week)


def test_selection_preserves_source_and_excludes_future_and_postseason():
    source = fixture()
    before = source.copy(deep=True)
    result = ResearchWindow(2026, 1).select(source, required=[], play_types=["pass"])
    assert result.game_id.tolist() == ["a"]
    result.loc[0, "week"] = 9
    pd.testing.assert_frame_equal(source, before)


@pytest.mark.parametrize(
    "column,value",
    [
        ("week", 1.5),
        ("week", 0),
        ("season", 2026.5),
        ("game_id", "  "),
        ("play_id", ""),
    ],
)
def test_invalid_snapshot_keys_and_periods(column, value):
    source = fixture().astype({column: object})
    source.loc[0, column] = value
    with pytest.raises(ValueError):
        ResearchWindow(2026, 1).select(source, required=[], play_types=["pass"])


def test_team_alias_and_flag_contract():
    frame = pd.DataFrame({"posteam": ["LAR", "JAC"], "flag": [0, 1]})
    assert normalize_teams(frame, ["posteam"]).posteam.tolist() == ["LA", "JAX"]
    require_binary_flags(frame, ["flag"])
    frame.loc[0, "flag"] = float("nan")
    with pytest.raises(ValueError, match="flag"):
        require_binary_flags(frame, ["flag"])


@pytest.mark.parametrize(
    "service", [ReceiverUsage(), TeamMatchups(), NeutralTendencies()]
)
def test_all_workflows_apply_same_window_validation(service):
    # Window is validated before metric-specific column validation.
    with pytest.raises(ValueError, match="season"):
        service.summarize(pd.DataFrame(), season=2026.5, through_week=1)
