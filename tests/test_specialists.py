import pandas as pd
import pytest

from fantasyfootball.reporting import render_specialists
from fantasyfootball.specialists import (
    BANDS,
    KickerBaseline,
    kicking_scores,
    specialist_context,
)


def kicking_row(**overrides):
    row = {
        "player_id": "k",
        "season": 2026,
        "week": 1,
        "team": "NE",
        "fg_blocked_list": "",
    }
    for col in [
        "fg_made",
        "fg_missed",
        "fg_blocked",
        "pat_made",
        "pat_missed",
        "pat_blocked",
    ]:
        row[col] = 0
    for band in BANDS:
        for prefix in ["fg_made_", "fg_missed_"]:
            row[prefix + band.replace("60p", "60_")] = 0
    row.update(overrides)
    return row


def test_distance_scoring_includes_blocks_and_stacks_penalties():
    frame = pd.DataFrame(
        [
            kicking_row(
                fg_made=2,
                fg_made_40_49=1,
                fg_made_60_=1,
                fg_missed=1,
                fg_missed_20_29=1,
                fg_blocked=1,
                fg_blocked_list="19",
                pat_made=2,
                pat_missed=1,
                pat_blocked=1,
            )
        ]
    )
    settings = {
        "fgm_40_49": 4,
        "fgm_60p": 6,
        "fgmiss": -1,
        "fgmiss_20_29": -1,
        "fgmiss_0_19": -1,
        "xpm": 1,
        "xpmiss": -1,
    }
    assert kicking_scores(frame, settings).tolist() == [6]
    with pytest.raises(ValueError, match="Unsupported"):
        kicking_scores(frame, {"fgm_yds_over_30": 0.1})
    frame["fg_blocked_list"] = ""
    with pytest.raises(ValueError, match="mismatch"):
        kicking_scores(frame, settings)


def test_kicker_prediction_is_past_only_and_requires_current_team_history():
    data = pd.DataFrame([kicking_row(week=w, pat_made=w) for w in range(1, 8)])
    model = KickerBaseline().fit(data, {"xpm": 1}, 2026, 7)
    changed = data.copy()
    changed.loc[changed.week == 7, "pat_made"] = 1000
    other = KickerBaseline().fit(changed, {"xpm": 1}, 2026, 7)
    assert model.cutoff == 202606
    assert model.predict("k", "NE") == other.predict("k", "NE") == (3.5, 6)
    assert model.predict("k", "NYJ") == (None, 0)
    with pytest.raises(ValueError, match="duplicate"):
        KickerBaseline().fit(pd.concat([data, data]), {"xpm": 1}, 2026, 7)


def specialist_fixture():
    roster = pd.DataFrame(
        [
            {
                "sleeper_id": "1",
                "player_id": "k",
                "player_name": "Kicker",
                "pos": "K",
                "starter_slot": "K1",
                "is_reserve": False,
                "is_taxi": False,
            },
            {
                "sleeper_id": "NYJ",
                "player_id": None,
                "player_name": None,
                "pos": None,
                "starter_slot": "DEF1",
                "is_reserve": False,
                "is_taxi": False,
            },
        ]
    )
    details = {
        "1": {
            "position": "K",
            "full_name": "<Kicker>",
            "team": "NE",
            "status": "Active",
        },
        "NYJ": {"position": "DEF", "team": "NYJ"},
    }
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 7,
                "game_type": "REG",
                "game_id": "game",
                "home_team": "NE",
                "away_team": "NYJ",
                "gameday": "2026-10-25",
                "gametime": "13:00",
            }
        ]
    )
    raw = pd.DataFrame([kicking_row(week=w, pat_made=3) for w in range(1, 7)])
    return roster, details, schedule, raw


def test_specialist_context_and_email_respect_locks_and_explain_defense(tmp_path):
    roster, details, schedule, raw = specialist_fixture()
    frame, audit = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"xpm": 1},
        season=2026,
        week=7,
        as_of="2026-10-25T12:00:00-04:00",
    )
    assert frame.opp.tolist() == ["NYJ", "NE"]
    assert frame.recommendation.tolist() == ["START (BASELINE)", "NOT MODELED"]
    assert pd.isna(frame.projected_points.iloc[1])
    frame.to_csv(tmp_path / "specialists.csv", index=False)
    html, plain, ids = render_specialists(tmp_path, audit)
    assert "&lt;Kicker&gt;" in html and "<Kicker>" not in html
    assert "DEF1" in plain and ids == {"1", "NYJ"}
    locked, _ = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"xpm": 1},
        season=2026,
        week=7,
        as_of="2026-10-25T14:00:00-04:00",
    )
    assert locked.recommendation.iloc[0] == "LOCKED STARTER"
    assert locked.availability.tolist() == ["locked_starter", "locked_starter"]
    details["1"]["injury_status"] = "Out"
    out, _ = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"xpm": 1},
        season=2026,
        week=7,
        as_of="2026-10-25T12:00:00-04:00",
    )
    assert out.availability.iloc[0] == "unavailable"
    assert pd.isna(out.projected_points.iloc[0])


def test_unsupported_kicker_rules_disable_estimates_not_offensive_report():
    roster, details, schedule, raw = specialist_fixture()
    frame, audit = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"fgm_yds": 0.1},
        season=2026,
        week=7,
        as_of="2026-10-25T12:00:00-04:00",
    )
    assert frame.projected_points.isna().all()
    assert "Unsupported" in audit["kicker_blocker"]


def test_multi_kicker_and_unknown_candidates_do_not_get_start_advice():
    roster, details, schedule, raw = specialist_fixture()
    result, _ = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"xpm": 1},
        season=2026,
        week=7,
        as_of="2026-10-25T12:00:00-04:00",
        kicker_slots=2,
    )
    assert result.recommendation.eq("NOT MODELED").all()
    second = roster.iloc[0].copy()
    second["sleeper_id"] = "2"
    second["player_id"] = "unknown"
    second["starter_slot"] = ""
    roster = pd.concat([roster, pd.DataFrame([second])], ignore_index=True)
    result, _ = specialist_context(
        roster,
        details,
        schedule,
        raw,
        {"xpm": 1},
        season=2026,
        week=7,
        as_of="2026-10-25T12:00:00-04:00",
    )
    assert "unknown" in result.availability.values
    assert result.recommendation.eq("NOT MODELED").all()
