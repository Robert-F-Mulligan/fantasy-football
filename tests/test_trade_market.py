from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from fantasyfootball.trading.market import FairnessAssessment, FantasyCalcMarket

NOW = datetime(2026, 11, 11, 18, tzinfo=timezone.utc)


def snapshot(league_type=1):
    return {
        "status": "available",
        "fetched_at": NOW.isoformat(),
        "source": "Test source",
        "league_type": league_type,
        "quotes": {"a": {"value": 100}, "b": {"value": 160}},
    }


def test_keeper_market_gap_does_not_claim_fairness_or_acceptance_probability():
    result = FairnessAssessment(snapshot(), now=NOW).assess(["a"], ["b"])
    assert result["player_market_comparison"]["receive_minus_give"] == 60
    assert result["player_market_comparison"]["symmetric_gap_percent"] == pytest.approx(
        60 / 130 * 100
    )
    assert result["status"] == "keeper_unresolved"
    assert (
        result["verdict"] == "not_established"
        and result["acceptance_probability"] is None
    )


def test_future_pick_cannot_be_treated_as_zero_or_a_dynasty_rookie_pick():
    result = FairnessAssessment(snapshot(), now=NOW).assess(
        [], ["b"], give_picks=[{"pick_id": "2027:1:3"}]
    )
    assert result["status"] == "unpriced_future_picks"
    assert result["player_market_comparison"] is None


def test_missing_price_and_stale_quotes_do_not_generate_a_verdict():
    assessor = FairnessAssessment(snapshot(), now=NOW)
    assert assessor.assess(["missing"], ["b"])["status"] == "incomplete_prices"
    assert (
        FairnessAssessment(snapshot(), now=NOW + timedelta(hours=25)).assess(
            ["a"], ["b"]
        )["status"]
        == "stale"
    )
    assert (
        FairnessAssessment(snapshot(), now=NOW - timedelta(seconds=1)).assess(
            ["a"], ["b"]
        )["status"]
        == "stale"
    )


def test_equal_redraft_prices_still_do_not_prove_acceptance_or_keeper_fairness():
    data = snapshot(0)
    data["quotes"]["b"]["value"] = 100
    result = FairnessAssessment(data, now=NOW).assess(["a"], ["b"])
    assert result["player_market_comparison"]["direction"] == "equal quoted values"
    assert result["verdict"] == "not_established"


def request_context():
    return {
        "waiver_settings": {"num_teams": 12, "type": 1, "max_keepers": 2},
        "roster_positions": ["QB", "RB", "FLEX"],
        "scoring_settings": {"rec": 1, "pass_td": 6},
    }


def test_provider_matches_exact_ids_and_preserves_format_and_scope():
    response = Mock()
    response.json.return_value = [
        {"player": {"sleeperId": "123", "name": "A", "position": "RB"}, "value": 400}
    ]
    session = Mock()
    session.get.return_value = response
    roster = pd.DataFrame(
        {
            "player_id": ["gsis-a", "gsis-b"],
            "sleeper_id": ["123", "other"],
            "pos": ["RB", "RB"],
        }
    )
    data = FantasyCalcMarket().fetch(
        request_context(), roster, session=session, now=NOW
    )
    assert data["status"] == "available" and set(data["quotes"]) == {"gsis-a"}
    assert session.get.call_args.kwargs["params"] == {
        "isDynasty": "false",
        "numQbs": 1,
        "numTeams": 12,
        "ppr": 1,
    }
    assert data["league_type"] == 1 and data["keeper_limit"] == 2


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [{"player": None, "value": 4}],
        [
            {
                "player": {"sleeperId": "123", "name": "A", "position": "RB"},
                "value": float("nan"),
            }
        ],
        [{"player": {"sleeperId": "123", "name": "A", "position": "RB"}, "value": -1}],
    ],
)
def test_bad_market_feed_is_unavailable_without_partial_prices(rows):
    response = Mock()
    response.json.return_value = rows
    session = Mock()
    session.get.return_value = response
    roster = pd.DataFrame({"player_id": ["a"], "sleeper_id": ["123"], "pos": ["RB"]})
    data = FantasyCalcMarket().fetch(
        request_context(), roster, session=session, now=NOW
    )
    assert data["status"] == "unavailable" and data["quotes"] == {}


def test_network_failure_keeps_valuation_unavailable_instead_of_failing_email():
    session = Mock()
    session.get.side_effect = requests.Timeout()
    assert (
        FantasyCalcMarket().fetch(
            request_context(), pd.DataFrame(), session=session, now=NOW
        )["status"]
        == "unavailable"
    )
