from types import SimpleNamespace

import pandas as pd
import pytest

from fantasyfootball.trading.service import TradeCalculator
from fantasyfootball.trading.value import RestOfSeasonValue
from fantasyfootball.reports.drop_review import acquisition_lines


def calculator():
    roster = pd.DataFrame([
        dict(player_id=p, player_name=p, pos=pos, roster_id=owner, tradable=True)
        for p, pos, owner in [("rb", "RB", 1), ("wr", "WR", 1), ("cook", "RB", 2)]
    ])
    forecasts = pd.DataFrame([
        dict(player_id=p, week=11, status="projected", projected_points=points)
        for p, points in [("rb", 10), ("wr", 9), ("cook", 20)]
    ])
    pool = pd.DataFrame(columns=["player_id", "pos"])
    alternatives = forecasts.iloc[:0].copy()
    rates = pd.DataFrame(dict(player_id=["rb", "wr", "cook"], probability=[1., 1., 1.]))
    slots = {"RB": ["RB"], "WR": ["WR"]}
    model = RestOfSeasonValue(roster, forecasts, pool, alternatives, rates, slots, [11])
    return TradeCalculator(roster, forecasts, slots, [11], value_model=model,
                           forecast_evidence={p: {"flags": []} for p in roster.player_id},
                           offer_fairness=SimpleNamespace(evidence={"keeper_limit": 0}))


def test_acquisition_preserves_other_position_and_runs_once_per_target(monkeypatch):
    import fantasyfootball.trading.evidence as evidence
    c = calculator()
    original = evidence.assess_drops
    calls = []
    def tracked(*args, **kwargs):
        calls.append(kwargs["incoming"])
        return original(*args, **kwargs)
    monkeypatch.setattr(evidence, "assess_drops", tracked)
    review = c.review_acquisition_drops(1, "cook")
    assert review["recommended_player_id"] == "rb"
    assert c.review_acquisition_drops(1, "cook") == review
    assert calls == ["cook"]
    rows = {r["player_id"]: r for r in review["candidates"]}
    assert rows["wr"]["loss_low"] == 9
    assert rows["rb"]["loss_high"] == 0


def test_legacy_snapshot_does_not_manufacture_freshness_or_keeper_clearance():
    c = calculator()
    c.forecast_evidence = {}
    assert c.review_acquisition_drops(1, "cook")["status"] == "unavailable"
    c.forecast_evidence = {p: {"flags": []} for p in c.roster.player_id}
    c.offer_fairness = None
    assert c.review_acquisition_drops(1, "cook")["keeper_review_required"]


@pytest.mark.parametrize("owner,pid", [(1, "rb"), (1, "missing"), (99, "cook")])
def test_invalid_acquisition_is_rejected(owner, pid):
    with pytest.raises(ValueError):
        calculator().review_acquisition_drops(owner, pid)


def test_target_review_explanation_identifies_conditional_options():
    c = calculator()
    review = c.review_acquisition_drops(1, "cook")
    text = " ".join(acquisition_lines(review))
    assert "After this acquisition" in text
    assert "rb (0.0-0.0" in text
    assert "wr (" not in text


def test_cli_can_review_roster_space_without_a_trade(tmp_path, monkeypatch):
    import json
    import sys
    import fantasyfootball.trading.__main__ as cli
    out = tmp_path / "review.json"
    monkeypatch.setattr(cli, "load_calculator", lambda _: (calculator(), {
        "my_roster": 1, "as_of": "2026-11-22", "history_cutoff": 202610}))
    monkeypatch.setattr(sys, "argv", ["trading", "--plan", str(tmp_path),
        "--review-drops-for", "cook", "--output", str(out)])
    cli.main()
    saved = json.loads(out.read_text())
    assert saved["incoming_player_id"] == "cook"
    assert saved["recommended_player_id"] == "rb"
