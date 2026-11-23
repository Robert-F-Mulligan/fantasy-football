import pytest

from fantasyfootball.evaluation.availability_archive import designation_history, follow_up


def observation(**changes):
    row = dict(league_id="private", roster_id=1, season=2026, week=11,
        player_id="p", sleeper_id="1", captured_at="2026-11-18T14:00:00Z",
        provider_fetched_at="2026-11-18T13:59:00Z", source_archive_sha256="a",
        pregame=True, kickoff="2026-11-22T18:00:00Z", injury_field_present=True,
        injury_designation="out", projected_points=8.)
    row.update(changes)
    return row


def test_null_designation_is_not_missing_field_or_medical_clearance():
    first=observation()
    second=observation(captured_at="2026-11-19T14:00:00Z",provider_fetched_at="2026-11-19T13:59:00Z",
                       source_archive_sha256="b",injury_designation=None)
    rows=designation_history([second,first])
    assert rows[1]["designation_removed"]
    assert rows[1]["previous_status_archive_sha256"]=="a"
    missing=dict(second,injury_field_present=False)
    assert not designation_history([first,missing])[1]["designation_removed"]
    assert "designation_removed" not in first


def test_repeated_or_stale_source_cannot_establish_a_transition():
    first=observation()
    stale=observation(captured_at="2026-11-19T14:00:00Z",source_archive_sha256="b",injury_designation=None)
    assert not designation_history([first,stale])[1]["designation_removed"]


def test_late_first_capture_is_not_replaced_by_a_better_forecast():
    first=observation(pregame=False,captured_at="2026-11-22T19:00:00Z")
    later=observation(captured_at="2026-11-22T20:00:00Z",source_archive_sha256="b",projected_points=20.)
    result=follow_up([later,first],{})
    assert result["selected_count"]==1
    assert result["selected_forecasts"][0]["outcome_status"]=="excluded_late_or_unknown_kickoff"
    assert result["scored_count"]==0


def test_missing_box_score_never_becomes_zero_or_dnp():
    result=follow_up([observation(injury_designation=None)],{})
    row=result["selected_forecasts"][0]
    assert row["actual_points"] is None and row["outcome_status"]=="unresolved"
    assert result["mae_observed_only"] is None


def test_followup_scores_explicit_finalized_observations_only():
    key=("private",1,2026,11,"p")
    outcome=dict(status="played",points=12.,source="verified boxscore",finalized_at="2026-11-23T14:00:00Z")
    result=follow_up([observation()],{key:outcome})
    assert result["mae_observed_only"]==4
    bad=dict(outcome,status="dnp")
    with pytest.raises(ValueError,match="zero"):
        follow_up([observation()],{key:bad})
    bad=dict(outcome,finalized_at="2026-11-18T12:00:00Z")
    with pytest.raises(ValueError,match="predates"):
        follow_up([observation()],{key:bad})


def test_missing_prediction_is_coverage_not_zero_forecast():
    key=("private",1,2026,11,"p")
    result=follow_up([observation(projected_points=None)],{key:dict(status="played",points=12.,
        source="verified",finalized_at="2026-11-23T14:00:00Z")})
    assert result["selected_forecasts"][0]["actual_points"]==12
    assert result["scored_count"]==0


def test_verified_archive_integration_and_idempotent_private_output(tmp_path, monkeypatch):
    import hashlib
    import io
    import json
    import shutil
    from datetime import datetime, timezone
    import pandas as pd
    from test_evidence import sample
    from fantasyfootball.archives import evidence
    from fantasyfootball.evaluation.scorecard import ArchivedForecast
    from fantasyfootball.evaluation.availability_archive import read_observations, build_private_availability_history

    root=sample(tmp_path)
    (root/"league/import-report.json").write_text(json.dumps(dict(
        fetched_at="2026-10-28T13:55:00Z",league_id="test",roster_id=1)))
    (root/"league/league-supported-offense.json").write_text(json.dumps({"scoring":{"receiving_rec":1}}))
    players=json.dumps({"1":{"position":"QB","injury_status":None,"status":"Active"}}).encode()
    (root/"context/players.json").write_bytes(players)
    context=json.loads((root/"context/manifest.json").read_text())
    context["players.json"]["sha256"]=hashlib.sha256(players).hexdigest()
    (root/"context/manifest.json").write_text(json.dumps(context))
    (root/"plan/availability.csv").write_text("sleeper_id,player_id,roster_id,pos,kickoff,availability\n1,a,1,QB,2026-10-29T00:00:00Z,eligible\n")
    monkeypatch.setattr(evidence,"utc_now",lambda:datetime(2026,10,28,14,tzinfo=timezone.utc))
    path=evidence.capture(root,tmp_path/"archive")
    rows=read_observations(path)
    assert rows[0]["injury_field_present"] and rows[0]["injury_designation"] is None
    assert rows[0]["confirmed_game_active"] is None
    assert rows[0]["pregame"] and rows[0]["projected_points"]==10
    checkout=tmp_path/"private"
    destination=checkout/"snapshots/2026/week-08"/path.name
    destination.parent.mkdir(parents=True)
    shutil.copyfile(path,destination)
    current=ArchivedForecast(path)
    added=build_private_availability_history(current,checkout,pd.DataFrame(),("test",1))
    report=json.loads((checkout/added[0]).read_text())
    assert report["unresolved_count"]==1 and report["scored_count"]==0
    assert build_private_availability_history(current,checkout,pd.DataFrame(),("test",1))==[]


def test_changed_scoring_rules_cannot_silently_score_a_frozen_forecast():
    key=("private",1,2026,11,"p")
    result=follow_up([observation(scoring_sha256="old")],{key:dict(status="played",points=12.,
        source="verified",finalized_at="2026-11-23T14:00:00Z",scoring_sha256="new")})
    assert result["unresolved_count"]==1 and result["scored_count"]==0
