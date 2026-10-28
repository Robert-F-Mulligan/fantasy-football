import json
from types import SimpleNamespace

import pandas as pd

from fantasyfootball.lineups.weekly import WeeklyLineupPlanner
from fantasyfootball.reports.waivers import render_waivers
from fantasyfootball.waivers.service import FaabPolicy, candidates


def budget(used=0, minimum=0):
    return FaabPolicy(
        {
            "waiver_settings": {
                "waiver_type": 2,
                "waiver_budget": 100,
                "waiver_bid_min": minimum,
            },
            "waiver_budget_used": used,
        }
    )


def test_faab_caps_and_unknowns():
    assert budget(98).recommend(8)[:2] == (2, 2)
    assert budget(100).recommend(8)[:2] == (0, 0)
    assert budget(100, 1).recommend(8)[:2] == (None, None)
    assert budget().recommend(8, kicker=True)[:2] == (1, 3)
    assert budget().recommend(8, uncertain=True)[:2] == (1, 3)
    assert budget().recommend(0)[:2] == (0, 1)
    assert FaabPolicy({}).recommend(8)[:2] == (None, None)
    assert budget().recommend(float("nan"))[:2] == (None, None)
    assert budget(float("nan")).remaining is None


def test_owned_aliases_reserve_and_ambiguous_id_excluded():
    registry = SimpleNamespace(
        aliases=pd.DataFrame(
            [
                {"provider": "sleeper", "external_id": s, "player_id": p}
                for s, p in [("1", "a"), ("2", "a"), ("3", "b"), ("4", "c"), ("5", "c")]
            ]
        )
    )
    details = {str(i): {"position": "RB", "full_name": str(i)} for i in range(1, 7)}
    roster = pd.DataFrame([{"sleeper_id": "1", "player_id": "a"}])
    result = candidates(registry, details, roster, extra_owned=["3"])
    assert result.sleeper_id.tolist() == ["6"]
    assert (
        result.player_id.isna().all()
    )  # Retained for coverage; cannot be projected without identity.


def test_flex_gain_and_locked_slot():
    planner = WeeklyLineupPlanner()
    frame = pd.DataFrame(
        [
            {
                "player_id": pid,
                "player_name": pid,
                "pos": pos,
                "projected_points": points,
            }
            for pid, pos, points in [("a", "RB", 10), ("b", "WR", 8), ("c", "TE", 12)]
        ]
    )
    availability = frame.drop(columns="projected_points").assign(
        availability="eligible", locked_slot=""
    )
    slots = {"RB1": ["RB"], "FLEX1": ["RB", "WR", "TE"]}
    base = planner.recommend(frame.iloc[:2], availability.iloc[:2], slots)
    after = planner.recommend(frame, availability, slots)
    assert after.projected_points.sum() - base.projected_points.sum() == 4
    availability.loc[availability.player_id == "b", ["availability", "locked_slot"]] = [
        "locked_starter",
        "FLEX1",
    ]
    locked = planner.recommend(frame, availability, slots)
    assert locked.set_index("slot").loc["FLEX1", "player_id"] == "b"
    assert locked.projected_points.sum() == 18


def test_email_escapes_names_and_withholds_unmodeled_bids(tmp_path):
    pd.DataFrame(
        [
            {
                "category": "FLEX",
                "rank": 1,
                "player_name": "<script>",
                "pos": "TE",
                "opp": "NE",
                "projected_points": 12,
                "lineup_gain": 4,
                "faab_low": 3,
                "faab_high": 7,
                "warning": "Questionable",
            },
            {
                "category": "DEF",
                "rank": None,
                "player_name": "NYJ",
                "pos": "DEF",
                "opp": "NE",
                "projected_points": None,
                "lineup_gain": None,
                "faab_low": None,
                "faab_high": None,
                "warning": "",
            },
        ]
    ).to_csv(tmp_path / "waivers.csv", index=False)
    (tmp_path / "waiver-report.json").write_text(
        json.dumps(
            {
                "categories": ["FLEX", "DEF"],
                "remaining_faab": 50,
                "limits": "Heuristic",
                "lineup_gain_note": "Conditional",
            }
        ),
        encoding="utf-8",
    )
    html, plain = render_waivers(tmp_path)
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "$3-$7" in html and "unranked watchlist" in html
    assert "Defense points and FAAB not modeled" in plain


def test_tuesday_and_wednesday_delivery_records_are_independent():
    from hashlib import sha256
    from unittest.mock import Mock

    from fantasyfootball.reports.reporting import deliver_once

    class Ledger:
        def __init__(self):
            self.records = {}

        def ensure_branch(self):
            pass

        def get(self, key):
            return self.records.get(key), "sha"

        def put(self, key, value, sha=None):
            self.records[key] = value
            return "sha"

    ledger = Ledger()
    mailer = Mock()
    args = (ledger, mailer, "a@example.com", "123", 2026, 8, "subject", "text", "html")
    assert deliver_once(*args, report_type="waivers") == "sent"
    assert deliver_once(*args) == "sent"
    assert deliver_once(*args, report_type="waivers") == "already_sent"
    assert mailer.send.call_count == 2
    assert sha256(b"a@example.com:123:2026:8").hexdigest() in ledger.records


def test_email_has_one_defense_explanation_and_keeps_specific_flags(tmp_path):
    rows = []
    for name in ["A", "B"]:
        rows.append(
            dict(
                category="DEF",
                rank=None,
                player_name=name,
                pos="DEF",
                opp="NE",
                projected_points=None,
                lineup_gain=None,
                faab_low=None,
                faab_high=None,
                warning="Bye",
            )
        )
    rows.append(
        dict(
            category="FLEX",
            rank=1,
            player_name="Receiver",
            pos="WR",
            opp="NYJ",
            projected_points=8.0,
            lineup_gain=1.0,
            faab_low=1,
            faab_high=2,
            warning="Injury designation: Questionable; recheck before kickoff. Low volume; small sample; weak forecast.",
        )
    )
    pd.DataFrame(rows).to_csv(tmp_path / "waivers.csv", index=False)
    (tmp_path / "waiver-report.json").write_text(
        json.dumps(
            {
                "categories": ["DEF", "FLEX"],
                "limits": "Unrostered is not a guarantee of claim eligibility.",
                "lineup_gain_note": "Repeated boilerplate",
            }
        )
    )
    html, plain = render_waivers(tmp_path)
    for output in [html, plain]:
        assert output.count("Defense points and FAAB not modeled") == 1
        assert "Unrostered" not in output and "recheck before kickoff" not in output
        for flag in [
            "Bye",
            "Questionable",
            "Low volume",
            "small sample",
            "weak forecast",
        ]:
            assert flag in output
    assert "Unranked /" not in html
