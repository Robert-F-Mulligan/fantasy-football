import json
from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest

from fantasyfootball.evaluation.trades import (
    evaluate_trade_forecasts,
    seal_trade_forecasts,
)
from fantasyfootball.reports.trades import render_trades
from fantasyfootball.trading.audit import audit_trade_model


def fixture():
    players = pd.DataFrame(
        {
            "player_id": list("abcd"),
            "roster_id": [1, 1, 2, 2],
            "pos": ["RB"] * 4,
            "team": ["AAA", "AAA", "BBB", "BBB"],
        }
    )
    projections = pd.DataFrame(
        [
            {"player_id": p, "week": w, "status": "projected", "projected_points": v}
            for w in [10, 11]
            for p, v in zip("abcd", [10, 2, 20, 5])
        ]
    )
    model = SimpleNamespace(
        players=players.set_index("player_id"),
        projections=projections,
        replacement_ids=set(),
        probabilities=dict.fromkeys("abcd", 1),
    )
    calculator = SimpleNamespace(
        value_model=model, roster=players, slots={"RB": ["RB"]}
    )
    offer = {
        "give": ["b"],
        "receive": ["c"],
        "my_drops": [],
        "partner_drops": [],
        "partner_roster": 2,
    }
    report = {
        "season": 2026,
        "week": 10,
        "weeks": [10, 11],
        "as_of": "2026-11-11T15:00:00Z",
        "my_roster": 1,
        "opportunities": [offer, deepcopy(offer)],
    }
    history = pd.DataFrame(
        [
            {"player_id": p, "season": 2026, "week": w, "fantasy_points": v}
            for w in [6, 7, 8, 9]
            for p, v in zip("abcd", [8, 1, 12, 4])
        ]
    )
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": w,
                "game_type": "REG",
                "home_team": "AAA",
                "away_team": "BBB",
                "gameday": d,
                "gametime": "20:15",
                "home_score": 20,
                "away_score": 10,
            }
            for w, d in [(10, "2026-11-12"), (11, "2026-11-19")]
        ]
    )
    return calculator, report, history, schedule


def test_sealing_deduplicates_exposures_and_never_uses_future_history():
    c, r, h, s = fixture()
    a = seal_trade_forecasts(c, r, h, s)
    future = h.iloc[:4].assign(week=10, fantasy_points=9999)
    b = seal_trade_forecasts(c, r, pd.concat([h, future]), s)
    assert a == b and len(a["forecasts"]) == 2
    mine = next(f for f in a["forecasts"] if f["owner_id"] == 1)
    assert mine["model_gain"] == 20 and mine["recent_four_gain"] == 8
    assert mine["zero_gain"] == 0
    assert all(d["player_id"] in {"a", "c"} for d in mine["delta"])


def test_waits_for_full_horizon_and_never_turns_missing_outcomes_into_zero():
    c, r, h, s = fixture()
    document = seal_trade_forecasts(c, r, h, s)
    points = {(p, w): v for w in [10, 11] for p, v in zip("abcd", [10, 2, 20, 5])}
    early = evaluate_trade_forecasts(document, points, {10}, r["as_of"])
    assert early["scored_count"] == 0 and all(
        x["status"] == "awaiting_full_horizon" for x in early["rows"]
    )
    missing = dict(points)
    del missing[("c", 11)]
    assert (
        evaluate_trade_forecasts(document, missing, {10, 11}, r["as_of"])[
            "scored_count"
        ]
        == 0
    )
    final = evaluate_trade_forecasts(document, points, {10, 11}, r["as_of"])
    assert final["status"] == "complete" and final["paired_count"] == 2
    assert final["model_mae_paired"] == 0
    assert final["recent_four_mae_paired"] > 0 and final["zero_mae_paired"] > 0
    assert final["promotion_decision"] is None


def test_late_captures_and_corrupt_exposures_cannot_be_scored():
    c, r, h, s = fixture()
    document = seal_trade_forecasts(c, r, h, s)
    late = evaluate_trade_forecasts(document, {}, set(), "2026-11-13T15:00:00Z")
    assert all(x["status"] == "late_or_unverifiable_capture" for x in late["rows"])
    broken = deepcopy(document)
    broken["forecasts"][0]["delta"].append(broken["forecasts"][0]["delta"][0])
    with pytest.raises(ValueError, match="exposure"):
        evaluate_trade_forecasts(broken, {}, set(), r["as_of"])
    broken = deepcopy(document)
    broken["history_cutoff"] = 202610
    with pytest.raises(ValueError, match="pregame"):
        evaluate_trade_forecasts(broken, {}, set(), r["as_of"])


def test_unknown_keeper_rules_stay_unknown_and_price_ceiling_disabled():
    audit = audit_trade_model(
        {"rules": {"round_penalty": 2, "max_consecutive_keeps": 2}}, {}
    )
    assert len(audit["unresolved_keeper_rules"]) == 4
    assert not audit["price_guidance_enabled"]
    assert any(f["code"] == "mixed_value_scales" for f in audit["findings"])


def test_brief_separates_future_proxy_cost_and_omits_false_precision():
    _, r, _, _ = fixture()
    r.update(
        status="estimated",
        league_team_count=12,
        opportunities=[],
        model_audit=audit_trade_model({}, {}),
        players={
            "c": {"name": "Target", "pos": "RB", "team": "BBB"},
            "b": {"name": "Drop", "pos": "RB", "team": "AAA"},
        },
        pick_trade_scenarios={
            "offers": [
                {
                    "target_id": "c",
                    "status": "estimated",
                    "pick": {
                        "season": 2027,
                        "round": 3,
                        "original_roster": 1,
                        "value_scenario": {"selection": "3.12"},
                    },
                    "reference": {"my_total_change": 6.450477},
                    "trade": {
                        "my_gain": 75.5,
                        "partner_gain": -83.7,
                        "my_drops": ["b"],
                        "offer_estimate": {
                            "my_future_change": {"low": -107, "high": -40},
                            "partner_future_change": {"low": 20, "high": 100},
                        },
                    },
                }
            ]
        },
    )
    _, plain, html = render_trades(r, "Team")
    assert "future-cost proxy" in html and "no validated fair-price ceiling" in plain
    assert "6.450477" not in html and "Your reference net" not in html
    assert "recent-four-game" in plain and "Current-season lineup change" in plain


def test_private_archive_chooses_earliest_trade_capture(tmp_path, monkeypatch):
    from zipfile import ZipFile

    from fantasyfootball.evaluation import trade_archive

    c, r, h, s = fixture()
    document = seal_trade_forecasts(c, r, h, s)
    snapshots = tmp_path / "snapshots" / "2026" / "week-10"
    snapshots.mkdir(parents=True)

    def make(name, captured):
        path = snapshots / name
        manifest = {"season": 2026, "week": 10, "captured_at": captured}
        with ZipFile(path, "w") as z:
            z.writestr("evidence-manifest.json", json.dumps(manifest))
            z.writestr(
                "league/import-report.json",
                json.dumps({"league_id": "123", "roster_id": 1}),
            )
            z.writestr(
                "league/league-supported-offense.json",
                json.dumps({"scoring": {"rushing_yds": 0.1}}),
            )
            z.writestr("plan/trade-prospective.json", json.dumps(document))
        return path

    early = make("early.zip", "2026-11-11T15:00:00Z")
    make("later.zip", "2026-11-12T15:00:00Z")

    def verified(path):
        with ZipFile(path) as z:
            return json.loads(z.read("evidence-manifest.json"))

    monkeypatch.setattr(trade_archive, "verify", verified)
    current = SimpleNamespace(
        manifest={"captured_at": "2026-11-30T15:00:00Z"},
        sha256="outcome",
        history=pd.DataFrame(
            [
                {
                    "player_id": p,
                    "season": 2026,
                    "week": w,
                    "team": "AAA" if p in "ab" else "BBB",
                    "rushing_yds": v * 10,
                }
                for w in [10, 11]
                for p, v in zip("abcd", [10, 2, 20, 5])
            ]
        ),
    )
    added = trade_archive.build_private_trade_scorecards(
        current, tmp_path, s, ("123", 1)
    )
    assert len(added) == 1
    import hashlib

    result = json.loads((tmp_path / added[0]).read_text())
    assert (
        result["forecast_archive_sha256"]
        == hashlib.sha256(early.read_bytes()).hexdigest()
    )
    assert result["status"] == "complete"
    assert (
        trade_archive.build_private_trade_scorecards(current, tmp_path, s, ("123", 1))
        == []
    )
