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
