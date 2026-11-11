import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd
import pytest

from fantasyfootball.reports import hosted
from fantasyfootball.trading.deadline import trade_window


def schedule():
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 11,
                "game_type": "REG",
                "gameday": day,
                "gametime": "20:15",
            }
            for day in ["2026-11-19", "2026-11-23"]
        ]
    )


def test_deadline_remains_open_after_thursday_and_describes_end_not_kickoff():
    window = trade_window(
        {"trade_deadline": 11, "trade_review_days": 2},
        schedule(),
        2026,
        "2026-11-20T12:00:00-05:00",
    )
    assert window["allow_email"]
    assert "November 23, 2026" in window["description"]
    assert "kickoff is not" in window["description"]
    assert window["review_days"] == 2


@pytest.mark.parametrize(
    "now",
    [
        "2026-11-23T20:15:00-05:00",
        "2026-11-24T10:00:00-05:00",
        "2026-12-01T10:00:00-05:00",
    ],
)
def test_final_game_email_guard_never_guesses_end_time(now):
    assert not trade_window({"trade_deadline": 11}, schedule(), 2026, now)[
        "allow_email"
    ]


def test_no_deadline_and_disabled_trading():
    assert trade_window(
        {"trade_deadline": 0}, schedule(), 2026, "2026-12-01T10:00:00Z"
    )["allow_email"]
    assert not trade_window(
        {"trade_deadline": 0, "disable_trades": 1},
        schedule(),
        2026,
        "2026-12-01T10:00:00Z",
    )["allow_email"]


def test_unknown_deadline_schedule_fails_closed():
    with pytest.raises(ValueError, match="unavailable"):
        trade_window({"trade_deadline": 12}, schedule(), 2026, "2026-11-20T12:00:00Z")


def test_preparation_suppresses_before_stats_or_email(tmp_path, monkeypatch):
    context = tmp_path / "context"
    context.mkdir()
    schedule().to_csv(context / "games.csv", index=False)
    monkeypatch.setattr(hosted, "sync_weekly_context", lambda _: context)
    client = Mock()
    client.get.return_value = {"season": "2026", "settings": {"trade_deadline": 11}}
    monkeypatch.setattr("fantasyfootball.data.sleeper.SleeperClient", lambda: client)
    sync = Mock()
    monkeypatch.setattr(hosted, "DataSyncService", sync)
    out = tmp_path / "report"
    assert (
        hosted.prepare(
            out,
            "123",
            "Team",
            2026,
            now=datetime(2026, 11, 24, 15, tzinfo=timezone.utc),
            report_type="trades",
        )
        == "trade_suppressed"
    )
    sync.assert_not_called()
    assert hosted.send(out) == "trade_suppressed"


def test_delayed_send_rechecks_live_deadline_before_reservation_or_smtp(
    tmp_path, monkeypatch
):
    (tmp_path / "delivery.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "report_type": "trades",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "league_id": "123",
                "season": 2026,
            }
        )
    )
    guard = Mock(return_value={"allow_email": False})
    monkeypatch.setattr("fantasyfootball.trading.deadline.live_trade_window", guard)
    ledger, smtp = Mock(), Mock()
    monkeypatch.setattr(hosted, "GitHubDeliveryLedger", ledger)
    monkeypatch.setattr(hosted, "GmailSMTP", smtp)
    assert hosted.send(tmp_path) == "trade_suppressed"
    ledger.assert_not_called()
    smtp.assert_not_called()
    guard.assert_called_once()
