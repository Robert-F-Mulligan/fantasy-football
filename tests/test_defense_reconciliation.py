import pandas as pd
import pytest

from fantasyfootball.evaluation.defense_reconciliation import (
    DefenseComponentReconciliation,
)


def candidate(team="LA", count=2):
    return {
        "season": 2026,
        "week": 1,
        "team": team,
        "scoring_key": "sack",
        "source_count": count,
        "candidate_component_points": count,
        "game_id": "game",
    }


def observation(team="LAR", value=2):
    return {
        "season": "2026",
        "week": 1,
        "player_id": team,
        "player": {"position": "DEF"},
        "category": "stat",
        "season_type": "regular",
        "stats": {"sack": value},
    }


def compare(rows, records):
    return DefenseComponentReconciliation().compare(
        pd.DataFrame(rows), records, season=2026, through_week=1
    )


def test_aliases_explicit_zero_and_mismatch_are_compared():
    report, detail = compare(
        [candidate(), candidate("NE", 0), candidate("BUF", 4)],
        [observation(), observation("NE", 0), observation("BUF", 3)],
    )
    assert list(detail.status) == ["mismatch", "matched", "matched"]
    assert report["components"][0]["matched_rows"] == 2
    assert report["components"][0]["mismatched_rows"] == 1
    assert report["ready_for_scoring"] is False


@pytest.mark.parametrize("value", [None, "bad", float("inf"), -1])
def test_invalid_observations_are_not_zero(value):
    report, detail = compare([candidate(count=0)], [observation(value=value)])
    assert detail.status.iloc[0] == "missing_or_invalid_observation"
    assert report["components"][0]["paired_rows"] == 0


def test_sparse_fields_and_absent_team_weeks_remain_visible():
    sparse = observation()
    sparse["stats"] = {}
    report, detail = compare(
        [candidate(), candidate("NE")], [sparse, observation("BUF")]
    )
    assert set(detail.status) == {
        "missing_or_invalid_observation",
        "missing_provider_team_week",
        "missing_source_team_week",
    }
    assert report["components"][0]["unresolved_rows"] == 3


def test_duplicate_source_and_provider_fail():
    with pytest.raises(ValueError, match="Duplicate candidate"):
        compare([candidate(), candidate()], [observation()])
    with pytest.raises(ValueError, match="Duplicate Sleeper"):
        compare([candidate()], [observation(), observation("LA")])


def test_filters_projection_postseason_and_other_weeks():
    records = [
        observation(),
        dict(observation(), category="projection"),
        dict(observation(), season_type="post"),
        dict(observation(), week=2),
    ]
    report, _ = compare([candidate()], records)
    assert report["provider_team_weeks"] == 1
    with pytest.raises(ValueError, match="finite integers"):
        compare([candidate()], [dict(observation(), week=1.5)])
