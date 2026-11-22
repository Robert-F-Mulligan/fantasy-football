import pandas as pd
import pytest

from fantasyfootball.trading.evidence import assess_drops, player_evidence
from fantasyfootball.reports.drop_review import review_lines


def fixture():
    roster = pd.DataFrame([
        dict(player_id="return", player_name="Returning RB", sleeper_id="1", roster_id=1, pos="RB", team="A", tradable=True),
        dict(player_id="depth", player_name="Depth RB", sleeper_id="2", roster_id=1, pos="RB", team="A", tradable=True),
    ])
    history = pd.DataFrame([dict(player_id="return", season=2026, week=w, team="A", fantasy_points=18) for w in [1, 2, 3, 4]])
    schedule = pd.DataFrame([dict(season=2026, week=w, game_type="REG", home_team="A", away_team="B") for w in range(1, 12)])
    projections = pd.DataFrame([dict(player_id=p, week=w, status="projected", projected_points=v) for w in [10, 11] for p, v in [("return", 7), ("depth", 10)]])
    replacements = pd.DataFrame(columns=["player_id", "pos"])
    alternatives = pd.DataFrame(columns=projections.columns)
    rates = pd.DataFrame(dict(player_id=["return", "depth"], probability=[.5, 1.]))
    return roster, history, schedule, projections, replacements, alternatives, rates


def test_clear_designation_does_not_erase_history_gap_or_imply_medical_clearance():
    roster, history, schedule, *_ = fixture()
    e = player_evidence(roster, history, schedule, {"1": {"injury_status": None}}, 2026, 10)
    assert e["return"]["last_observed_period"] == 202604
    assert e["return"]["scheduled_games_since_observation"] == 5
    assert "workload_after_gap_unverified" in e["return"]["flags"]
    assert "injury_designation" not in e["return"]["flags"]
    future = pd.concat([history, pd.DataFrame([dict(player_id="return", season=2026, week=10, team="A", fantasy_points=99)])])
    assert player_evidence(roster, future, schedule, {}, 2026, 10) == e


def test_byes_are_not_missing_games_and_injury_is_separate():
    roster, history, schedule, *_ = fixture()
    schedule = schedule[schedule.week.le(4)]
    e = player_evidence(roster, history, schedule, {"1": {"injury_status": "Out"}}, 2026, 10)
    assert e["return"]["flags"] == ["injury_designation"]
    assert e["return"]["scheduled_games_since_observation"] == 0


def test_returning_player_can_reverse_drop_order_without_mutating_baseline():
    roster, history, schedule, projections, pool, alternatives, rates = fixture()
    e = player_evidence(roster, history, schedule, {}, 2026, 10)
    result = assess_drops(roster, 1, projections, pool, alternatives, rates, {"RB": ["RB"]}, [10, 11], e)
    rows = {r["player_id"]: r for r in result["candidates"]}
    assert rows["return"]["scenario_losses"]["historical_participation"] == 0
    assert rows["return"]["scenario_losses"]["full_availability_historical_workload"] == 16
    assert result["status"] == "review_required"
    assert result["recommended_player_id"] is None
    assert rates.probability.tolist() == [.5, 1.]
    assert projections.projected_points.tolist() == [7, 10, 7, 10]


def test_near_ties_and_keeper_rights_prevent_false_precision():
    roster, _, _, projections, pool, alternatives, rates = fixture()
    projections["projected_points"] = 10
    rates["probability"] = 1
    args = (roster, 1, projections, pool, alternatives, rates, {"RB": ["RB"]}, [10, 11], {})
    result = assess_drops(*args)
    assert result["status"] == "near_tie"
    assert set(result["shortlist"]) == {"return", "depth"}
    assert assess_drops(*args, keeper_limit=2)["status"] == "review_required"
    projections.loc[0, "status"] = "unknown"
    assert assess_drops(*args)["status"] == "incomplete"


def test_scenarios_preserve_known_byes_and_injury_unavailability():
    roster, history, schedule, projections, pool, alternatives, rates = fixture()
    projections.loc[projections.player_id.eq("return"), "status"] = "unavailable"
    e = player_evidence(roster, history, schedule, {}, 2026, 10)
    result = assess_drops(roster, 1, projections, pool, alternatives, rates, {"RB": ["RB"]}, [10, 11], e)
    row = next(r for r in result["candidates"] if r["player_id"] == "return")
    assert row["loss_high"] == 0


def test_report_exposes_cutoff_gap_and_scenario_limits():
    roster, history, schedule, projections, pool, alternatives, rates = fixture()
    e = player_evidence(roster, history, schedule, {}, 2026, 10)
    assessment = assess_drops(roster, 1, projections, pool, alternatives, rates, {"RB": ["RB"]}, [10, 11], e, keeper_limit=2)
    lines = " ".join(review_lines(dict(drop_assessment=assessment, player_evidence=e, forecast_cutoff=202609)))
    assert "202609" in lines and "202604" in lines
    assert "Keeper value is not included" in lines
    assert "not confidence intervals" in lines
    assert "workload after gap unverified" in lines
