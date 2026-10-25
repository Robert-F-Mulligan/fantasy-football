import json
from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from fantasyfootball.hosted import require_recent_coverage, target_week
from fantasyfootball.reporting import GmailSMTP, deliver_once, render_report


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


def test_report_escapes_source_text_and_discloses_limitations(tmp_path):
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
    assert "Week 8" in subject
    assert "\u2014" in subject
    assert '<meta charset="utf-8">' in html
    assert "\u00e2\u20ac\u201d" not in html
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
    monkeypatch.setattr("fantasyfootball.reporting.smtplib.SMTP_SSL", factory)
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
