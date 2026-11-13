import pandas as pd
import pytest

from fantasyfootball.evaluation.defense_events import DefenseEventAudit


def play(**changes):
    row = {
        "season": 2026,
        "week": 1,
        "season_type": "REG",
        "game_id": "g1",
        "play_id": 1,
        "home_team": "A",
        "away_team": "B",
        "posteam": "A",
        "defteam": "B",
        "play_type": "run",
        "down": 4,
        "fourth_down_failed": 1,
        "fourth_down_converted": 0,
        "penalty": 0,
        "touchdown": 0,
        "fumble": 0,
        "fumbled_1_team": "A",
        "fumbled_2_team": None,
        "fumble_recovery_1_team": "B",
        "fumble_recovery_2_team": None,
        "forced_fumble_player_1_team": "B",
        "forced_fumble_player_2_team": None,
        "fumble_forced": 1,
        "fumble_out_of_bounds": 0,
    }
    return {**row, **changes}


def audit(rows, complete=False):
    return DefenseEventAudit().audit(
        pd.DataFrame(rows),
        season=2026,
        through_week=1,
        complete_game_ids=["g1"] if complete else [],
    )


def component(candidates, key, team="B"):
    return candidates.loc[
        candidates.team.eq(team) & candidates.scoring_key.eq(key)
    ].iloc[0]


def test_partial_coverage_keeps_observed_count_without_inventing_total():
    report, counts, events = audit([play()])
    assert not report["ready_for_scoring"]
    assert counts.source_count.isna().all()
    assert component(counts, "def_4_and_stop").observed_source_count == 1
    assert events.iloc[0].play_id == 1
    assert events.iloc[0].team == "B"


def test_complete_attestation_and_deterministic_order():
    rows = [play(play_id=2, fourth_down_failed=0, fourth_down_converted=1), play()]
    _, counts, events = audit(rows, complete=True)
    assert component(counts, "def_4_and_stop").source_count == 1
    assert component(counts, "def_4_and_stop", "A").source_count == 0
    _, other, evidence = audit(list(reversed(rows)), complete=True)
    pd.testing.assert_frame_equal(counts, other)
    pd.testing.assert_frame_equal(events, evidence)


@pytest.mark.parametrize("kind", ["punt", "field_goal"])
def test_kicks_are_not_fourth_down_stops(kind):
    _, counts, events = audit([play(play_type=kind, fourth_down_failed=0)], True)
    assert component(counts, "def_4_and_stop").source_count == 0
    assert events.empty


def test_no_play_excluded_but_penalty_unresolved():
    _, counts, events = audit(
        [play(play_type="no_play", fumble=1), play(play_id=2, penalty=1)], True
    )
    assert events.play_id.tolist() == [2]
    assert events.status.tolist() == ["unresolved"]
    assert pd.isna(component(counts, "def_4_and_stop").source_count)
    assert component(counts, "def_4_and_stop").observed_source_count == 0


@pytest.mark.parametrize(
    "kind,recovery,force",
    [
        ("run", "fum_rec", "ff"),
        ("pass", "fum_rec", "ff"),
        ("punt", "def_st_fum_rec", "def_st_ff"),
        ("kickoff", "def_st_fum_rec", "def_st_ff"),
    ],
)
def test_single_fumble_attribution(kind, recovery, force):
    _, counts, events = audit(
        [play(play_type=kind, down=1, fourth_down_failed=0, fumble=1)], True
    )
    assert component(counts, recovery).source_count == 1
    assert component(counts, force).source_count == 1
    assert len(events) == 2


def test_special_teams_uses_explicit_team_not_initial_defteam():
    _, counts, _ = audit(
        [
            play(
                play_type="punt",
                fourth_down_failed=0,
                fumble=1,
                fumbled_1_team="B",
                fumble_recovery_1_team="A",
                forced_fumble_player_1_team="A",
            )
        ],
        True,
    )
    assert component(counts, "def_st_fum_rec", "A").source_count == 1
    assert component(counts, "def_st_ff", "A").source_count == 1


def test_own_recovery_is_not_takeaway_and_unforced_not_forced():
    _, counts, events = audit(
        [
            play(
                down=1,
                fourth_down_failed=0,
                fumble=1,
                fumble_recovery_1_team="A",
                fumble_forced=0,
                forced_fumble_player_1_team=None,
            )
        ],
        True,
    )
    assert component(counts, "fum_rec").source_count == 0
    assert component(counts, "ff").source_count == 0
    assert events.empty


@pytest.mark.parametrize(
    "changes",
    [
        {"fumbled_2_team": "B"},
        {"fumbled_1_team": None},
        {"fumble_recovery_1_team": None},
    ],
)
def test_complex_or_missing_recovery_is_unknown(changes):
    _, counts, _ = audit(
        [play(down=1, fourth_down_failed=0, fumble=1, **changes)], True
    )
    assert pd.isna(component(counts, "fum_rec").source_count)
    assert component(counts, "fum_rec").observed_source_count == 0


def test_missing_columns_do_not_turn_into_zero():
    row = play(down=1, fourth_down_failed=0, fumble=1)
    del row["fumbled_2_team"]
    _, counts, _ = audit([row], True)
    assert pd.isna(component(counts, "fum_rec").source_count)
    row = play()
    del row["fumble"]
    _, counts, _ = audit([row], True)
    assert pd.isna(component(counts, "fum_rec").source_count)


def test_missing_forcing_team_does_not_inherit_defteam():
    _, counts, _ = audit(
        [
            play(
                down=1, fourth_down_failed=0, fumble=1, forced_fumble_player_1_team=None
            )
        ],
        True,
    )
    assert pd.isna(component(counts, "ff").source_count)
    assert component(counts, "fum_rec").source_count == 1


def test_conflicting_fourth_down_indicators_unknown():
    _, counts, _ = audit([play(fourth_down_converted=1)], True)
    assert pd.isna(component(counts, "def_4_and_stop").source_count)


def test_duplicate_and_conflicting_identity_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        audit([play(), play()])
    with pytest.raises(ValueError, match="Conflicting"):
        audit([play(), play(play_id=2, away_team="C")])


@pytest.mark.parametrize("turnover", ["interception", "fumble"])
def test_defensive_return_touchdowns_have_explicit_attribution(turnover):
    _, counts, events = audit(
        [
            play(
                down=1,
                fourth_down_failed=0,
                touchdown=1,
                td_team="B",
                return_touchdown=1,
                **{turnover: 1},
            )
        ],
        True,
    )
    assert component(counts, "def_td").source_count == 1
    assert events.loc[events.scoring_key.eq("def_td"), "team"].tolist() == ["B"]


@pytest.mark.parametrize(
    "changes", [{"td_team": "A"}, {"play_type": "kickoff"}, {"play_type": "punt"}]
)
def test_offensive_and_special_team_tds_not_defensive_tds(changes):
    row = play(
        down=1,
        fourth_down_failed=0,
        touchdown=1,
        td_team="B",
        return_touchdown=1,
        fumble=1,
    )
    _, counts, _ = audit([{**row, **changes}], True)
    assert component(counts, "def_td").source_count == 0


def test_unattributed_and_penalty_tds_not_counted():
    _, counts, _ = audit(
        [play(touchdown=1, td_team="B", return_touchdown=1, fumble=1, penalty=1)], True
    )
    assert pd.isna(component(counts, "def_td").source_count)
