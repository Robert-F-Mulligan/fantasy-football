import hashlib
import json
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from fantasyfootball.archives import evidence


def sample(tmp_path):
    root = tmp_path / "report"

    def save(name, value):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        content = value if isinstance(value, bytes) else json.dumps(value).encode()
        p.write_bytes(content)
        return hashlib.sha256(content).hexdigest()

    observed = "2026-10-28T13:55:00Z"
    save(
        "plan/plan-report.json",
        {
            "status": "offensive_lineup_created",
            "season": 2026,
            "week": 8,
            "history_cutoff": 202607,
            "as_of": observed,
        },
    )
    games = save("context/games.csv", b"game_id\ngame1\n")
    players = save("context/players.json", {"1": {"position": "QB"}})
    save(
        "context/manifest.json",
        {
            n: {"sha256": h, "fetched_at": observed}
            for n, h in [("games.csv", games), ("players.json", players)]
        },
    )
    save("data/current.json", {"snapshot": "snapshots/test"})
    weekly = save("data/snapshots/test/weekly.csv", b"player_id\na\n")
    save(
        "data/snapshots/test/manifest.json",
        {
            "files": {"weekly.csv": weekly},
            "sources": {"stats": {"fetched_at": observed}},
        },
    )
    save("league/import-report.json", {"fetched_at": observed})
    for name in ["league-supported-offense.json", "offensive-slots.json", "slots.json"]:
        save("league/" + name, {})
    for name in ["rosters.csv", "my_roster.csv"]:
        save("league/" + name, b"player_id\na\n")
    save(
        "plan/availability.csv",
        b"sleeper_id,kickoff\n1,2026-10-29T00:00:00Z\n2,2026-10-28T14:00:00Z\n3,\n",
    )
    for name in ["projections.csv", "lineup.csv"]:
        save("plan/" + name, b"player_id,projected_points\na,10\n")
    save(".env", b"SECRET=never-copy")
    save("report.html", b"private mail not needed for evaluation")
    return root


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(
        evidence, "utc_now", lambda: datetime(2026, 10, 28, 14, tzinfo=timezone.utc)
    )


def test_capture_is_append_only_verifiable_and_allowlisted(tmp_path, clock):
    root = sample(tmp_path)
    first = evidence.capture(root, tmp_path / "archive")
    second = evidence.capture(root, tmp_path / "archive")
    assert first != second and first.exists()
    manifest = evidence.verify(first)
    assert [r["pregame_evidence"] for r in manifest["eligibility"]] == [
        True,
        False,
        False,
    ]
    assert not manifest["forecast_provenance_recorded"]
    assert "capture_runtime" in manifest
    with ZipFile(first) as z:
        assert ".env" not in z.namelist() and "report.html" not in z.namelist()


def test_old_report_cannot_be_backdated_by_as_of(tmp_path, monkeypatch):
    root = sample(tmp_path)
    monkeypatch.setattr(
        evidence, "utc_now", lambda: datetime(2026, 11, 1, 14, tzinfo=timezone.utc)
    )
    manifest = evidence.verify(evidence.capture(root, tmp_path / "archive"))
    assert not any(r["pregame_evidence"] for r in manifest["eligibility"])
    assert manifest["captured_at"].startswith("2026-11-01")


def test_future_sources_and_modified_context_fail(tmp_path, clock):
    root = sample(tmp_path)
    path = root / "context/players.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="checksum"):
        evidence.capture(root, tmp_path / "archive")
    raw = path.read_bytes()
    m = json.loads((root / "context/manifest.json").read_text())
    m["players.json"].update(
        sha256=hashlib.sha256(raw).hexdigest(), fetched_at="2026-11-01T00:00:00Z"
    )
    (root / "context/manifest.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="future"):
        evidence.capture(root, tmp_path / "archive")


def test_tampered_archive_is_rejected_without_extracting(tmp_path, clock):
    archive = evidence.capture(sample(tmp_path), tmp_path / "archive")
    target = tmp_path / "modified.zip"
    with (
        ZipFile(archive) as source,
        ZipFile(target, "w", compression=ZIP_DEFLATED) as out,
    ):
        for name in source.namelist():
            out.writestr(
                name,
                b"changed" if name == "plan/projections.csv" else source.read(name),
            )
    with pytest.raises(ValueError, match="checksum"):
        evidence.verify(target)
    with ZipFile(tmp_path / "bad.zip", "w") as out:
        out.writestr("../escape", "bad")
    with pytest.raises(ValueError, match="Unsafe"):
        evidence.verify(tmp_path / "bad.zip")


def test_invalid_training_cutoff_is_rejected(tmp_path, clock):
    root = sample(tmp_path)
    path = root / "plan/plan-report.json"
    m = json.loads(path.read_text())
    m["history_cutoff"] = 202608
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError, match="training cutoff"):
        evidence.capture(root, tmp_path / "archive")


def test_eligibility_requires_timezone_and_unique_identity():
    with pytest.raises(ValueError, match="timezone"):
        evidence.eligibility(
            pd.DataFrame({"sleeper_id": ["1"], "kickoff": ["2026-10-29"]}),
            "2026-10-28T14:00:00Z",
        )
    with pytest.raises(ValueError, match="unique"):
        evidence.eligibility(
            pd.DataFrame({"sleeper_id": ["1", "1"], "kickoff": ["", ""]}),
            "2026-10-28T14:00:00Z",
        )


def test_shadow_files_are_sealed_and_checksums_enforced(tmp_path, clock):
    root = sample(tmp_path)
    history = root / "plan/shadow-history.csv"
    history.write_bytes(b"player_id,period\na,202607\n")
    (root / "plan/shadow-projections.csv").write_bytes(
        b"player_id,baseline_points,candidate_points\na,10,11\n"
    )
    metadata = {
        "status": "recorded",
        "history_cutoff": 202607,
        "generated_at": "2026-10-28T13:58:00Z",
        "sources": [{"fetched_at": "2026-10-28T13:56:00Z"}],
        "history_sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(
            (root / "plan/projections.csv").read_bytes()
        ).hexdigest(),
    }
    (root / "plan/shadow-report.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    archive = evidence.capture(root, tmp_path / "archive")
    with ZipFile(archive) as z:
        assert "plan/shadow-projections.csv" in z.namelist()
        assert "plan/shadow-history.csv" in z.namelist()
    history.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Shadow evidence checksum"):
        evidence.capture(root, tmp_path / "archive")


def test_add_drop_comparisons_are_in_private_archive(tmp_path, clock):
    root = sample(tmp_path)
    payload = b"add_player_id,drop_player_id,net_gain\nx,a,2.0\n"
    (root / "plan/waiver-add-drop.csv").write_bytes(payload)
    (root / "plan/waiver-coverage.csv").write_bytes(b"week,status\n9,schedule_only\n")
    archive = evidence.capture(root, tmp_path / "archive")
    evidence.verify(archive)
    with ZipFile(archive) as z:
        assert z.read("plan/waiver-add-drop.csv") == payload
        assert "plan/waiver-coverage.csv" in z.namelist()


def independent_report(root, report_type):
    plan_path = root / "plan/plan-report.json"
    plan = json.loads(plan_path.read_text())
    plan.update(status="blocked", reason="Unresolved offensive player")
    plan_path.write_text(json.dumps(plan))
    (root / "plan/lineup.csv").unlink()
    (root / "delivery.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "report_type": report_type,
                "season": 2026,
                "week": 8,
            }
        )
    )
    if report_type == "trades":
        report = {"status": "estimated", "season": 2026, "week": 8, "as_of": plan["as_of"]}
        (root / "plan/trade-report.json").write_text(json.dumps(report))
        (root / "plan/trade-prospective.json").write_text("{}")
        for name in ["trade-projections.csv", "trade-rosters.csv"]:
            (root / "plan" / name).write_text("player_id\na\n")
    else:
        (root / "plan/waiver-report.json").write_text(
            json.dumps(
                {
                    "status": "ready",
                    "as_of": plan["as_of"],
                }
            )
        )
        for name in ["waivers.csv", "waiver-availability.csv"]:
            (root / "plan" / name).write_text("player_id\na\n")


@pytest.mark.parametrize("report_type", ["trades", "waivers"])
def test_blocked_lineup_preserves_independent_report(tmp_path, clock, report_type):
    from fantasyfootball.evaluation.scorecard import ArchivedForecast, WeeklyScorecard

    root = sample(tmp_path)
    independent_report(root, report_type)
    (root / "league/league-supported-offense.json").write_text('{"scoring": {}}')
    archive = evidence.capture(root, tmp_path / "archive")
    manifest = evidence.verify(archive)
    assert manifest["report_type"] == report_type
    assert manifest["lineup_status"] == "blocked"
    with ZipFile(archive) as sealed:
        assert "plan/lineup.csv" not in sealed.namelist()
        assert (
            json.loads(sealed.read("plan/plan-report.json"))["reason"]
            == "Unresolved offensive player"
        )
    forecast = ArchivedForecast(archive)
    assert forecast.lineup is None
    regret = WeeklyScorecard().lineup_regret(forecast, pd.DataFrame())
    assert regret["status"] == "unavailable"
    assert "Unresolved offensive player" in regret["reason"]


@pytest.mark.parametrize("report_type", ["trades", "waivers"])
def test_blocked_lineup_needs_completed_matching_report(tmp_path, clock, report_type):
    root = sample(tmp_path)
    independent_report(root, report_type)
    name = "trade-report.json" if report_type == "trades" else "waiver-report.json"
    path = root / "plan" / name
    report = json.loads(path.read_text())
    report["status"] = "unavailable"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Independent report is not complete"):
        evidence.capture(root, tmp_path / "archive")
    report["status"] = "estimated" if report_type == "trades" else "ready"
    report["as_of"] = "2026-10-27T13:55:00Z"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="timestamp does not match"):
        evidence.capture(root, tmp_path / "archive")


def test_lineup_capture_still_requires_completed_lineup(tmp_path, clock):
    root = sample(tmp_path)
    independent_report(root, "waivers")
    (root / "delivery.json").unlink()
    with pytest.raises(ValueError, match="Only completed plans"):
        evidence.capture(root, tmp_path / "archive")
    path = root / "plan/plan-report.json"
    plan = json.loads(path.read_text())
    plan["status"] = "offensive_lineup_created"
    path.write_text(json.dumps(plan))
    with pytest.raises(FileNotFoundError):
        evidence.capture(root, tmp_path / "archive")
