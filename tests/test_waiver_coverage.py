import pandas as pd

from fantasyfootball.waivers.coverage import ScheduleCoverage


def inputs():
    roster = pd.DataFrame(
        [
            {"player_id": "r", "sleeper_id": "1", "pos": "RB"},
            {"player_id": "w", "sleeper_id": "2", "pos": "WR"},
        ]
    ).assign(is_reserve=False, is_taxi=False)
    available = pd.DataFrame(
        [
            {
                "player_id": "x",
                "sleeper_id": "3",
                "pos": "WR",
                "is_reserve": False,
                "is_taxi": False,
            }
        ]
    )
    pairs = pd.DataFrame([{"add_player_id": "x", "drop_player_id": "r"}])
    details = {"1": {"team": "A"}, "2": {"team": "B"}, "3": {"team": "C"}}
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": w,
                "game_type": "REG",
                "home_team": a,
                "away_team": b,
            }
            for w, a, b in [(9, "A", "B"), (10, "C", "D"), (11, "A", "C")]
        ]
    )
    return (
        pairs,
        roster,
        available,
        details,
        schedule,
        {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]},
    )


def test_one_player_cannot_cover_both_position_and_flex():
    assert (
        ScheduleCoverage.filled(
            {"r": "RB"}, {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]}
        )
        == 1
    )
    # Matching must reassign a flexible player to accommodate a more constrained slot.
    assert (
        ScheduleCoverage.filled(
            {"r": "RB", "w": "WR"}, {"A": ["RB", "WR"], "B": ["RB", "TE"]}
        )
        == 2
    )


def test_future_gap_and_coverage_improvement_are_visible():
    result = ScheduleCoverage().evaluate(*inputs(), season=2026, week=8)
    assert result.before_filled.tolist() == [2, 0, 1]
    assert result.after_filled.tolist() == [1, 1, 1]
    text = ScheduleCoverage.summarize(result)
    assert "W9: 2/2 -> 1/2" in text and "W10: 0/2 -> 1/2" in text


def test_missing_schedule_or_unknown_team_is_not_a_zero():
    args = list(inputs())
    args[4] = args[4].loc[args[4].week.ne(10)]
    result = ScheduleCoverage().evaluate(*args, season=2026, week=8)
    assert result.loc[result.week.eq(10), "status"].item() == "unknown"
    assert "W10: unknown" in ScheduleCoverage.summarize(result)
    args = list(inputs())
    args[3]["3"]["team"] = None
    assert (
        ScheduleCoverage()
        .evaluate(*args, season=2026, week=8)
        .status.eq("unknown")
        .all()
    )


def test_reserve_excluded_and_rams_alias_supported():
    args = list(inputs())
    args[1].loc[args[1].player_id.eq("w"), "is_reserve"] = True
    assert ScheduleCoverage().evaluate(
        *args, season=2026, week=8
    ).before_filled.tolist() == [1, 0, 1]
    args = list(inputs())
    args[3]["1"]["team"] = "LAR"
    args[4]["home_team"] = args[4].home_team.replace({"A": "LA"})
    assert ScheduleCoverage().evaluate(
        *args, season=2026, week=8
    ).before_filled.tolist() == [2, 0, 1]


def test_end_of_season_and_invalid_duplicate_team_schedule():
    assert ScheduleCoverage().evaluate(*inputs(), season=2026, week=18).empty
    args = list(inputs())
    args[4] = pd.concat([args[4], args[4].iloc[:1]])
    assert (
        ScheduleCoverage().evaluate(*args, season=2026, week=8).iloc[0].status
        == "unknown"
    )
