"""Compare complete offensive lineups, not standalone player point sums."""

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from fantasyfootball.trading.needs import RosterNeedsPolicy
from fantasyfootball.trading.picks import validate_pick_exchange


class TradeCalculator:
    def __init__(
        self,
        roster,
        projections,
        slots,
        weeks,
        pick_inventory=None,
        value_model=None,
        fairness=None,
    ):
        self.needs_policy = RosterNeedsPolicy()
        self.value_model = value_model
        self.fairness = fairness
        self.pick_inventory = pick_inventory
        self.roster = roster.copy()
        self.roster["player_id"] = self.roster.player_id.astype(str)
        if roster.player_id.isna().any() or self.roster.player_id.duplicated().any():
            raise ValueError("Trade rosters need unique resolved player IDs")
        if not set(roster.pos).issubset({"QB", "RB", "WR", "TE"}):
            raise ValueError("Trade calculator supports offensive players only")
        if not slots or any(
            not p or not set(p).issubset({"QB", "RB", "WR", "TE"})
            for p in slots.values()
        ):
            raise ValueError("Explicit offensive slot eligibility is required")
        if (
            "tradable" not in self.roster
            or not self.roster.tradable.isin([True, False]).all()
        ):
            raise ValueError("Explicit tradable flags are required")
        self.slots = slots
        self.weeks = tuple(sorted(set(weeks)))
        if not self.weeks or any(
            isinstance(w, bool) or int(w) != w or not 1 <= w <= 18 for w in self.weeks
        ):
            raise ValueError("Choose regular-season weeks 1 through 18")
        p = projections.copy()
        p["player_id"] = p.player_id.astype(str)
        if p.duplicated(["player_id", "week"]).any():
            raise ValueError("Duplicate player-week projections")
        if not set(p.status).issubset({"projected", "bye", "unavailable", "unknown"}):
            raise ValueError("Unknown projection status")
        p["projected_points"] = pd.to_numeric(p.projected_points, errors="coerce")
        if not np.isfinite(p.loc[p.status.eq("projected"), "projected_points"]).all():
            raise ValueError("Projected points must be finite")
        self.projections = p.set_index(["player_id", "week"])
        self.players = self.roster.set_index("player_id")
        self._lineup = lru_cache(maxsize=20000)(self._lineup)

    def _lineup(self, ids, week):
        if self.value_model is not None:
            return self.value_model.weekly(ids, week)
        available = []
        for pid in ids:
            if (pid, week) not in self.projections.index:
                return None
            row = self.projections.loc[(pid, week)]
            if row.status == "unknown":
                return None
            if row.status == "projected":
                available.append(
                    (pid, self.players.loc[pid, "pos"], float(row.projected_points))
                )
        n = len(self.slots)
        # Dummy vacancies allow explicit shortfalls. Real players take priority,
        # including negative projections; a required slot is not voluntarily empty.
        bonus = (sum(abs(p[2]) for p in available) + 1) * 2
        scores = np.zeros((n, len(available) + n))
        for i, positions in enumerate(self.slots.values()):
            for j, (_, pos, points) in enumerate(available):
                scores[i, j] = points + bonus if pos in positions else -np.inf
        _rows, cols = linear_sum_assignment(-scores)
        chosen = [available[col] for col in cols if col < len(available)]
        return {"points": sum(p[2] for p in chosen), "filled": len(chosen), "slots": n}

    def evaluate(
        self,
        my_roster,
        partner_roster,
        give,
        receive,
        my_drops=(),
        partner_drops=(),
        *,
        give_picks=(),
        receive_picks=(),
    ):
        if my_roster == partner_roster:
            raise ValueError("Choose a different trade partner")
        sent_picks, gained_picks = validate_pick_exchange(
            self.pick_inventory,
            my_roster,
            partner_roster,
            list(give_picks),
            list(receive_picks),
        )
        groups = [tuple(map(str, x)) for x in (give, receive, my_drops, partner_drops)]
        give, receive, my_drops, partner_drops = groups
        if (
            (not give and not sent_picks)
            or (not receive and not gained_picks)
            or any(len(x) != len(set(x)) for x in groups)
        ):
            raise ValueError("Both trade sides need assets with unique player/pick IDs")
        if sum(map(len, groups)) != len(set().union(*map(set, groups))):
            raise ValueError("Trade and drop lists must not overlap")
        mine = set(self.roster.loc[self.roster.roster_id.eq(my_roster), "player_id"])
        theirs = set(
            self.roster.loc[self.roster.roster_id.eq(partner_roster), "player_id"]
        )
        if (
            not mine
            or not theirs
            or not set(give + my_drops).issubset(mine)
            or not set(receive + partner_drops).issubset(theirs)
        ):
            raise ValueError(
                "Every traded/dropped player must belong to the specified team"
            )
        if not self.players.loc[list(give + receive), "tradable"].all():
            raise ValueError(
                "Injured or inactive players are outside this trade scenario"
            )
        after_mine = mine.difference(give + my_drops).union(receive)
        after_theirs = theirs.difference(receive + partner_drops).union(give)
        if len(after_mine) > len(mine) or len(after_theirs) > len(theirs):
            raise ValueError(
                "Trades cannot increase active roster size; specify necessary drops"
            )
        weekly = []
        for week in self.weeks:
            values = [
                self._lineup(tuple(sorted(ids)), week)
                for ids in [mine, after_mine, theirs, after_theirs]
            ]
            if any(v is None for v in values):
                weekly.append({"week": week, "status": "unknown"})
                continue
            a, b, c, d = values
            weekly.append(
                {
                    "week": week,
                    "status": "estimated",
                    "my_before": a,
                    "my_after": b,
                    "partner_before": c,
                    "partner_after": d,
                    "my_gain": b["points"] - a["points"],
                    "partner_gain": d["points"] - c["points"],
                }
            )
        complete = all(r["status"] == "estimated" for r in weekly)
        result = {
            "status": "estimated" if complete else "incomplete",
            "partner_roster": partner_roster,
            "give_picks": sent_picks,
            "receive_picks": gained_picks,
            "pick_inventory_status": self.pick_inventory.get("status")
            if self.pick_inventory
            else None,
            "future_pick_value": None,
            "pick_capital_index_net": (
                sum(p["value_scenario"]["capital_index"] for p in gained_picks)
                - sum(p["value_scenario"]["capital_index"] for p in sent_picks)
            )
            if (sent_picks or gained_picks)
            and all("value_scenario" in p for p in sent_picks + gained_picks)
            else None,
            "valuation_scope": "Current-season lineup effect only; future picks are unpriced",
            "give": list(give),
            "receive": list(receive),
            "my_drops": list(my_drops),
            "partner_drops": list(partner_drops),
            "weekly": weekly,
            "my_gain": sum(r["my_gain"] for r in weekly) if complete else None,
            "partner_gain": sum(r["partner_gain"] for r in weekly)
            if complete
            else None,
        }

        result["recommendation"] = self.needs_policy.assess(
            self, mine, after_mine, result
        )
        result["fairness"] = (
            self.fairness.assess(list(give), list(receive), sent_picks, gained_picks)
            if self.fairness
            else {
                "verdict": "not_established",
                "status": "unavailable",
                "reason": "No market snapshot supplied",
                "player_market_comparison": None,
            }
        )
        return result

    def opportunities(self, my_roster, limit=5):
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("Opportunity limit must be a positive integer")
        mine = self.roster.loc[
            self.roster.roster_id.eq(my_roster) & self.roster.tradable
        ]
        others = self.roster.loc[
            ~self.roster.roster_id.eq(my_roster) & self.roster.tradable
        ]
        results = []
        for a in mine.itertuples():
            for b in others.itertuples():
                result = self.evaluate(
                    my_roster, b.roster_id, [a.player_id], [b.player_id]
                )
                if (
                    result["status"] == "estimated"
                    and result["recommendation"]["eligible"]
                    and round(result["my_gain"], 1) > 0
                    and round(result["partner_gain"], 1) > 0
                ):
                    results.append(result)
        results.sort(
            key=lambda r: (
                -r["my_gain"],
                -r["partner_gain"],
                r["give"],
                r["receive"],
            )
        )
        # Avoid presenting five variations involving the same trade partner.
        selected, partners = [], set()
        for row in results:
            if row["partner_roster"] not in partners:
                selected.append(row)
                partners.add(row["partner_roster"])
            if len(selected) == limit:
                break
        return selected
