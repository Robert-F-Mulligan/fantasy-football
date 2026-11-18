import json
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from fantasyfootball.reports.hosted import require_recent_coverage, target_week
from fantasyfootball.reports.reporting import GmailSMTP, deliver_once, render_report


class Ledger:
    def __init__(self):
        self.record = None
        self.puts = []

    def ensure_branch(self):
        pass

    def get(self, key):
        return self.record, "sha"

    def put(self, key, record, sha=None):
        self.record = record
        self.puts.append(record.copy())
        return "sha"


def delivery(ledger, mailer):
    return deliver_once(
        ledger,
        mailer,
        "test@example.com",
        "123",
        2026,
        8,
        "Subject",
        "Text",
        "<p>Text</p>",
    )


def test_successful_send_is_not_repeated():
    ledger = Ledger()
    mailer = Mock()
    assert delivery(ledger, mailer) == "sent"
    assert [r["status"] for r in ledger.puts] == ["pending", "sent"]
    assert delivery(ledger, mailer) == "already_sent"
    mailer.send.assert_called_once()


def test_ambiguous_send_failure_stays_pending_and_cannot_retry():
    ledger = Ledger()
    mailer = Mock()
    mailer.send.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        delivery(ledger, mailer)
    assert ledger.record["status"] == "pending"
    with pytest.raises(RuntimeError, match="uncertain"):
        delivery(ledger, mailer)
    mailer.send.assert_called_once()


def test_failed_reservation_does_not_send():
    ledger = Ledger()
    ledger.put = Mock(side_effect=RuntimeError("network"))
    mailer = Mock()
    with pytest.raises(RuntimeError):
        delivery(ledger, mailer)
    mailer.send.assert_not_called()


def schedule():
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 8,
                "game_type": "REG",
                "gameday": "2026-10-29",
                "gametime": "20:15",
                "home_team": "NYJ",
                "away_team": "NE",
                "home_score": None,
                "away_score": None,
            }
        ]
    )


def test_target_week_and_offseason():
    data = schedule()
    assert target_week(data, 2026, "2026-10-28T10:00:00-04:00") == 8
    assert target_week(data, 2026, "2026-11-10T10:00:00-05:00") is None
    assert target_week(data, 2025, "2026-10-28T10:00:00-04:00") is None


def test_prior_week_must_be_complete_and_include_both_teams():
    games = schedule()
    history = pd.DataFrame({"season": [2026], "week": [8], "team": ["NYJ"]})
    with pytest.raises(ValueError, match="incomplete"):
        require_recent_coverage(games, history, 2026, 9)
    games[["home_score", "away_score"]] = [20, 10]
    with pytest.raises(ValueError, match="scheduled teams"):
        require_recent_coverage(games, history, 2026, 9)
    history = pd.concat(
        [history, pd.DataFrame({"season": [2026], "week": [8], "team": ["NE"]})]
    )
    require_recent_coverage(games, history, 2026, 9)


@pytest.mark.parametrize("with_specialists", [False, True])
def test_report_escapes_source_text_and_discloses_limitations(
    tmp_path, with_specialists
):
    audit = {
        "status": "offensive_lineup_created",
        "as_of": "2026-10-28T14:00:00Z",
        "history_cutoff": 202607,
        "unsupported_scoring": {"st_ff": 1},
    }
    (tmp_path / "plan-report.json").write_text(json.dumps(audit))
    roster = pd.DataFrame(
        {
            "player_id": ["a", "b"],
            "player_name": ["<script>x</script>", "Bench"],
            "sleeper_id": ["1", "2"],
            "pos": ["QB", "QB"],
            "opp": ["NE", "BUF"],
            "availability": ["eligible", "eligible"],
            "warning": ["questionable", ""],
            "starter_slot": ["QB1", ""],
        }
    )
    if with_specialists:
        specialists = pd.DataFrame(
            {
                "player_id": [None, None, None],
                "player_name": ["Kicker", "Defense A", "Defense B"],
                "sleeper_id": ["3", "NYJ", "BUF"],
                "pos": ["K", None, "DEF"],
                "availability": ["unsupported_position"] * 3,
                "starter_slot": ["K1", "DEF1", ""],
            }
        )
        roster = pd.concat([roster, specialists], ignore_index=True)
        specialists.assign(
            pos=["K", "DEF", "DEF"],
            projected_points=[8.0, None, None],
            recommendation="Review",
            model_note="Separate specialist context",
        ).to_csv(tmp_path / "specialists.csv", index=False)
    roster.to_csv(tmp_path / "availability.csv", index=False)
    pd.DataFrame({"player_id": ["a", "b"], "projected_points": [10, 20]}).to_csv(
        tmp_path / "projections.csv", index=False
    )
    pd.DataFrame(
        {
            "slot": ["QB1"],
            "player_id": ["b"],
            "player_name": ["Bench"],
            "projected_points": [20],
        }
    ).to_csv(tmp_path / "lineup.csv", index=False)
    subject, _plain, html = render_report(tmp_path, "Team", 2026, 8)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "+10.0 projected points" in html
    assert "st_ff" in html and "not modeled" in html
    assert html.index("Recommended starters") < html.index(
        "Prediction ranges unavailable"
    )
    assert "Waiver wire" not in html
    assert "Week 8" in subject
    assert "\u2014" in subject
    assert '<meta charset="utf-8">' in html
    assert "\u00e2\u20ac\u201d" not in html
    if with_specialists:
        assert "Defense A" in html and "Defense B" in html and "Kicker" in html
        assert html.count("Defense A") == 1
    # Real duplicate offensive identities must still fail closed.
    pd.concat([roster, roster.iloc[[0]]]).to_csv(
        tmp_path / "availability.csv", index=False
    )
    with pytest.raises(pd.errors.MergeError):
        render_report(tmp_path, "Team", 2026, 8)
    audit["status"] = "blocked"
    audit["reason"] = "missing player"
    (tmp_path / "plan-report.json").write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="missing player"):
        render_report(tmp_path, "Team", 2026, 8)


def test_smtp_uses_tls_and_multipart_without_logging_secret(monkeypatch):
    context = MagicMock()
    smtp = context.__enter__.return_value
    smtp.send_message.return_value = {}
    factory = Mock(return_value=context)
    monkeypatch.setattr("fantasyfootball.reports.reporting.smtplib.SMTP_SSL", factory)
    GmailSMTP("sender@example.com", "secret").send(
        "to@example.com", "Test", "Plain", "<p>HTML</p>", "<id@example.com>"
    )
    assert factory.call_args.args == ("smtp.gmail.com", 465)
    smtp.login.assert_called_once_with("sender@example.com", "secret")
    message = smtp.send_message.call_args.args[0]
    assert message["To"] == "to@example.com"
    assert message.get_body(preferencelist=("html",)).get_content_charset() == "utf-8"
    assert message.get_body(preferencelist=("plain",)).get_content_charset() == "utf-8"
    assert (
        message.get_body(preferencelist=("html",)).get_content().strip()
        == "<p>HTML</p>"
    )


def blocked_plan(path, reason="Cannot fill all roster slots with eligible players"):
    path.mkdir(parents=True, exist_ok=True)
    (path / "plan-report.json").write_text(
        json.dumps(
            {
                "status": "blocked",
                "reason": reason,
                "season": 2026,
                "week": 8,
                "offensive_slots": {"QB1": ["QB"], "FLEX": ["RB", "WR", "TE"]},
                "as_of": "2026-10-28T14:00:00Z",
                "history_cutoff": 202607,
            }
        )
    )
    pd.DataFrame(
        {
            "player_id": ["a", "b", "c"],
            "sleeper_id": ["1", "2", "3"],
            "player_name": ["<script>Out</script>", "Bye Player", "Reserve Player"],
            "pos": ["WR", "RB", "TE"],
            "starter_slot": ["WR1", "RB1", ""],
            "availability": ["unavailable", "no_scheduled_game", "reserve"],
            "injury_status": ["out", "", "ir"],
            "warning": ["<b>check</b>", "Bye", ""],
        }
    ).to_csv(path / "availability.csv", index=False)
    pd.DataFrame({"player_id": [], "projected_points": []}).to_csv(
        path / "projections.csv", index=False
    )


def test_blocked_alert_is_opt_in_and_has_no_fabricated_lineup(tmp_path):
    blocked_plan(tmp_path)
    with pytest.raises(ValueError, match="Cannot email"):
        render_report(tmp_path, "Team", 2026, 8)
    title, plain, html = render_report(tmp_path, "<Team>", 2026, 8, allow_blocked=True)
    assert "Availability Alert" in title
    assert title == "<Team> - Week 8 Roster Availability Alert (2026)"
    assert "\u00e2\u20ac\u201d" not in html
    for text in [
        "Cannot fill all roster slots",
        "Bye Player",
        "Reserve Player",
        "No projected gain",
        "not a full lineup recommendation",
        "before kickoff",
        "QB1: 0 eligible players",
        "same player may count",
    ]:
        assert text in plain and text in html
    assert "&lt;script&gt;" in html and "&lt;Team&gt;" in html
    assert "<script>" not in html and "<b>check</b>" not in html
    assert "Recommended starters" not in html and "START" not in html
    assert not (tmp_path / "lineup.csv").exists()


@pytest.mark.parametrize(
    "reason",
    [
        "Resolve unknown player availability before recommending a lineup",
        "Every eligible or locked player needs a projection",
    ],
)
def test_alert_does_not_hide_input_failures(tmp_path, reason):
    blocked_plan(tmp_path, reason)
    with pytest.raises(ValueError, match=reason):
        render_report(tmp_path, "Team", 2026, 8, allow_blocked=True)


@pytest.mark.parametrize("blocked", [False, True])
def test_hosted_records_alert_variant_only_for_blocked_lineup(
    tmp_path, monkeypatch, blocked
):
    from datetime import datetime, timezone

    from fantasyfootball.reports import hosted

    context = tmp_path / "context"
    context.mkdir()
    schedule().to_csv(context / "games.csv", index=False)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    pd.DataFrame({"season": [2026], "week": [7], "team": ["NE"]}).to_csv(
        snapshot / "weekly.csv", index=False
    )
    monkeypatch.setattr(hosted, "sync_weekly_context", lambda path: context)
    monkeypatch.setattr(
        hosted, "DataSyncService", lambda: Mock(sync=Mock(return_value=(snapshot, {})))
    )
    monkeypatch.setattr(hosted, "require_recent_coverage", lambda *args: None)
    monkeypatch.setattr(hosted, "load_registry", lambda path: {})
    importer = Mock()
    importer.fetch.return_value = {
        "report": {"unsupported_slots": [], "draft_config_supported": True}
    }
    monkeypatch.setattr(hosted, "SleeperLeagueImporter", lambda: importer)

    def plan(args):
        blocked_plan(args.output)
        if not blocked:
            path = args.output / "plan-report.json"
            audit = json.loads(path.read_text())
            audit["status"] = "offensive_lineup_created"
            path.write_text(json.dumps(audit))

    monkeypatch.setattr(hosted, "write_weekly_plan", plan)
    if not blocked:
        renderer = Mock(return_value=("Lineup", "Text", "<p>Lineup</p>"))
        monkeypatch.setattr(hosted, "render_report", renderer)
    out = tmp_path / "prepared"
    assert (
        hosted.prepare(
            out,
            "123",
            "Team",
            2026,
            now=datetime(2026, 10, 28, 14, tzinfo=timezone.utc),
        )
        == "ready"
    )
    metadata = json.loads((out / "delivery.json").read_text())
    assert (metadata.get("report_variant") == "availability_alert") is blocked
    if blocked:
        assert "Availability Alert" in (out / "report.txt").read_text(encoding="utf-8")
    else:
        assert renderer.call_args.kwargs == {"allow_blocked": True}
