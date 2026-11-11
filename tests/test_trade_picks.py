from unittest.mock import Mock

import pandas as pd
import pytest

from fantasyfootball.trading.picks import fetch_pick_inventory
from fantasyfootball.trading.service import TradeCalculator


def source(*, future=False, traded=None, draft_type="snake", rounds=3):
    client = Mock()
    client.get.side_effect = [
        {"season": "2026", "settings": {"draft_rounds": 1}},
        [{"roster_id": 1}, {"roster_id": 2}],
        traded or [],
        [
            {
                "season": "2027" if future else "2026",
                "status": "pre_draft" if future else "complete",
                "type": draft_type,
                "settings": {"rounds": rounds, "teams": 2},
            }
        ],
    ]
    return client


def test_untraded_picks_are_owned_and_last_draft_rounds_are_provisional():
    inventory = fetch_pick_inventory("123", 2026, source())
    assert inventory["status"] == "provisional" and len(inventory["picks"]) == 6
    assert inventory["round_setting"] == 1 and inventory["rounds"] == 3
    pick = inventory["picks"][2]
    assert pick["pick_id"] == "2027:2:1" and pick["owner_id"] == 1
    assert (pick["overall_earliest"], pick["overall_latest"]) == (3, 4)


def test_transfer_uses_current_owner_not_original_roster():
    row = {
        "season": "2027",
        "round": 1,
        "roster_id": 1,
        "previous_owner_id": 1,
        "owner_id": 2,
    }
    inventory = fetch_pick_inventory("123", 2026, source(future=True, traded=[row]))
    pick = inventory["picks"][0]
    assert inventory["status"] == "configured"
    assert pick["original_roster"] == 1 and pick["owner_id"] == 2


def test_conflicting_pick_transfers_are_rejected():
    row = {"season": "2027", "round": 1, "roster_id": 1, "owner_id": 2}
    with pytest.raises(ValueError, match="Conflicting"):
        fetch_pick_inventory("123", 2026, source(traded=[row, row]))


def test_auction_does_not_invent_round_assets():
    inventory = fetch_pick_inventory("123", 2026, source(draft_type="auction"))
    assert inventory["status"] == "unavailable" and not inventory["picks"]


def calculator():
    inventory = fetch_pick_inventory("123", 2026, source())
    roster = pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "d"],
            "roster_id": [1, 1, 2, 2],
            "pos": ["RB"] * 4,
            "tradable": [True] * 4,
        }
    )
    projections = pd.DataFrame(
        {
            "player_id": ["a", "b", "c", "d"],
            "week": [8] * 4,
            "status": ["projected"] * 4,
            "projected_points": [10, 5, 15, 12],
        }
    )
    return TradeCalculator(roster, projections, {"RB1": ["RB"]}, [8], inventory)


def test_player_for_pick_requires_drop_and_does_not_price_future_pick_as_zero():
    c = calculator()
    with pytest.raises(ValueError, match="increase active roster"):
        c.evaluate(1, 2, [], ["c"], give_picks=["2027:1:1"])
    result = c.evaluate(1, 2, [], ["c"], my_drops=["b"], give_picks=["2027:1:1"])
    assert result["my_gain"] == 5 and result["partner_gain"] == -3
    assert result["future_pick_value"] is None
    assert result["give_picks"][0]["pick_id"] == "2027:1:1"
    assert result["pick_inventory_status"] == "provisional"


def test_pick_only_swap_has_zero_current_effect_but_unpriced_future_effect():
    result = calculator().evaluate(
        1, 2, [], [], give_picks=["2027:1:1"], receive_picks=["2027:2:2"]
    )
    assert result["my_gain"] == result["partner_gain"] == 0
    assert result["future_pick_value"] is None


@pytest.mark.parametrize(
    "give,receive",
    [(["2027:1:2"], []), (["2028:1:1"], []), (["2027:1:1"], ["2027:1:1"])],
)
def test_invalid_pick_proposals_are_rejected(give, receive):
    with pytest.raises(ValueError):
        calculator().evaluate(
            1, 2, ["a"], ["c"], give_picks=give, receive_picks=receive
        )


def test_confirmed_round_count_overrides_previous_draft_without_claiming_known_order():
    inventory = fetch_pick_inventory("123", 2026, source(rounds=3), confirmed_rounds=15)
    assert inventory["status"] == "rounds_confirmed" and len(inventory["picks"]) == 30
    assert inventory["rounds"] == 15 and "unassigned" in inventory["order_status"]


def test_confirmation_cannot_silently_override_configured_future_draft():
    with pytest.raises(ValueError, match="conflict"):
        fetch_pick_inventory(
            "123", 2026, source(future=True, rounds=3), confirmed_rounds=15
        )
