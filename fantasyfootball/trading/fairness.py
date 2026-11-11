"""Conditional two-season trade utility; scenario ranges are not confidence intervals."""

import itertools
import math

import pandas as pd


class OfferFairness:
    """Compare roster utility on a common point scale, separate from market prices."""

    def __init__(self, evidence):
        self.evidence = evidence

    @classmethod
    def build(
        cls,
        players,
        projections,
        replacements,
        alternatives,
        participation,
        *,
        season,
        weeks,
        inventory=None,
        rules=None,
        keeper_limit=0,
        draft_costs=None,
        history=None,
    ):
        probabilities = participation.set_index("player_id").probability.to_dict()
        frames = pd.concat([projections, alternatives], ignore_index=True)
        active = frames.loc[frames.status.eq("projected")].copy()
        active["expected"] = active.projected_points * active.player_id.map(
            probabilities
        )
        means = active.groupby("player_id").expected.mean().to_dict()
        historical_fallback = []
        if history is not None:
            past = history.loc[
                (history.season >= season - 1)
                & (history.season * 100 + history.week < season * 100 + min(weeks))
            ].sort_values(["season", "week"])
            for pid, rows in past.groupby("player_id"):
                if pid not in means and pid in probabilities and len(rows) >= 4:
                    means[pid] = (
                        float(rows.tail(8).fantasy_points.mean()) * probabilities[pid]
                    )
                    historical_fallback.append(pid)
        positions = (
            pd.concat([players, replacements]).set_index("player_id").pos.to_dict()
        )
        baselines = {}
        for pos in set(positions.values()):
            values = [
                means[p]
                for p in replacements.player_id
                if positions[p] == pos and p in means
            ]
            if values:
                baselines[pos] = max(values)
        annual = {
            p: 16 * max(0.0, v - baselines[positions[p]])
            for p, v in means.items()
            if positions[p] in baselines and math.isfinite(v)
        }
        return cls(
            {
                "version": 1,
                "season": season,
                "weeks": list(weeks),
                "annual_values": annual,
                "historical_fallback_player_ids": historical_fallback,
                "replacement_baselines": baselines,
                "curve": sorted(annual.values(), reverse=True),
                "keeper_limit": keeper_limit,
                "rules": rules or {},
                "draft_costs": draft_costs or {},
                "inventory": inventory,
                "assumptions": [
                    "Current per-game role and participation carried forward for 16 fantasy-season games; not a trained next-season forecast",
                    "Players without an active-week forecast use their last eight recorded games (minimum four) from this or last season; this assumes recovery for future valuation, not current availability",
                    "Future points are surplus over the best modeled current waiver alternative at each position",
                    "Draft curve ranks the observed player pool by projected surplus; rookies, offseason changes, and position-specific draft demand are not forecast",
                    "Ranks beyond observed positive surplus use replacement value, not a guaranteed worthless pick",
                    "Standings-based selections stressed by up to the league keeper capacity in either direction for keeper depletion and consumed picks",
                    "Keeper scenarios: no eligible rights; latest-round cost minus penalty; original-round cost where known, otherwise latest possible cost. Unknown consecutive counts are optimistic in eligible scenarios; confirmed two-time keepers are excluded",
                    "Latest-cost scenario excludes costs before Round 1; original-cost scenario floors them at Round 1. Costs and keeper counts follow players in eligible scenarios",
                    "Only owned picks can pay keeper costs; at most the league keeper limit; no pick can pay twice",
                    "Future utility weights 0.75 and 1.0 are sensitivity choices, not learned probabilities",
                    "Scenario extrema are not confidence intervals or guaranteed bounds; acceptance probability is not estimated",
                ],
            }
        )

    def _pick_value(self, pick, shift):
        ranks = pick.get("value_scenario", {}).get("projected_overall_picks")
        if not ranks:
            raise ValueError("Pick lacks projected draft positions")
        curve = self.evidence["curve"]
        values = []
        for rank in ranks:
            rank = max(1, int(rank) + shift)
            values.append(curve[rank - 1] if rank <= len(curve) else 0.0)
        return sum(values) / len(values)

    def _future(self, ids, picks, mode, shift):
        base = sum(self._pick_value(p, shift) for p in picks)
        limit = self.evidence["keeper_limit"]
        if mode == "none" or limit == 0:
            return base
        # Exact enumeration is deliberately limited to leagues with at most two keepers.
        rules = self.evidence["rules"]
        penalty = rules.get("round_penalty")
        max_keeps = rules.get("max_consecutive_keeps")
        if penalty is None or max_keeps is None:
            raise ValueError("Keeper penalty and consecutive limit are required")
        rounds = self.evidence["inventory"]["rounds"]
        choices = []
        for pid in ids:
            cost = self.evidence["draft_costs"].get(pid, {})
            if cost.get("consecutive_keeps", 0) >= max_keeps:
                continue
            if mode == "latest":
                rnd = cost.get("latest_round")
            else:
                rnd = cost.get("original_round", rounds)
            if rnd is None:
                rnd = rounds
            rnd -= penalty
            if rnd < 1:
                # Explicit alternate treatment of early-round eligibility.
                if mode == "latest":
                    continue
                rnd = 1
            for pick in picks:
                if pick["round"] != rnd:
                    continue
                surplus = self.evidence["annual_values"][pid] - self._pick_value(
                    pick, shift
                )
                if surplus > 0:
                    choices.append((pid, pick["pick_id"], surplus))
        best = max([0.0] + [c[2] for c in choices])
        if limit == 2:
            best = max(
                [best]
                + [
                    a[2] + b[2]
                    for a, b in itertools.combinations(choices, 2)
                    if a[0] != b[0] and a[1] != b[1]
                ]
            )
        return base + best

    def assess(self, calculator, my_roster, partner_roster, result):
        unavailable = {"status": "unavailable", "acceptance_probability": None}
        if result["status"] != "estimated":
            return {**unavailable, "reason": "Incomplete current-season projections"}
        e = self.evidence
        inventory = calculator.pick_inventory or e.get("inventory")
        if not inventory or not inventory.get("picks") or not e["curve"]:
            return {
                **unavailable,
                "reason": "Future pick inventory and player curve required",
            }
        if not 0 <= e["keeper_limit"] <= 2:
            return {
                **unavailable,
                "reason": "Keeper optimizer supports zero to two keepers",
            }
        mine = set(
            calculator.roster.loc[
                calculator.roster.roster_id.eq(my_roster), "player_id"
            ]
        )
        theirs = set(
            calculator.roster.loc[
                calculator.roster.roster_id.eq(partner_roster), "player_id"
            ]
        )
        after_mine = mine.difference(result["give"] + result["my_drops"]).union(
            result["receive"]
        )
        after_theirs = theirs.difference(
            result["receive"] + result["partner_drops"]
        ).union(result["give"])
        missing = sorted((mine | theirs) - e["annual_values"].keys())
        if missing:
            return {
                **unavailable,
                "reason": "Missing future role proxy",
                "missing_player_ids": missing,
            }
        sent = {p["pick_id"] for p in result["give_picks"]}
        received = {p["pick_id"] for p in result["receive_picks"]}
        my_picks = [p for p in inventory["picks"] if p["owner_id"] == my_roster]
        their_picks = [p for p in inventory["picks"] if p["owner_id"] == partner_roster]
        my_after = [p for p in my_picks if p["pick_id"] not in sent] + result[
            "receive_picks"
        ]
        their_after = [p for p in their_picks if p["pick_id"] not in received] + result[
            "give_picks"
        ]
        teams = len({p["original_roster"] for p in inventory["picks"]})
        shift_size = teams * e["keeper_limit"]
        scenarios = []
        # Preserve identical assumptions before/after and for both managers.
        try:
            for mode, shift, weight in itertools.product(
                ["none", "latest", "original"] if e["keeper_limit"] else ["none"],
                sorted({-shift_size, 0, shift_size}),
                [0.75, 1.0],
            ):
                my_future = self._future(
                    after_mine, my_after, mode, shift
                ) - self._future(mine, my_picks, mode, shift)
                their_future = self._future(
                    after_theirs, their_after, mode, shift
                ) - self._future(theirs, their_picks, mode, shift)
                scenarios.append(
                    {
                        "keeper_mode": mode,
                        "rank_shift": shift,
                        "future_weight": weight,
                        "my_future_change": my_future,
                        "partner_future_change": their_future,
                        "my_total_change": result["my_gain"] + weight * my_future,
                        "partner_total_change": result["partner_gain"]
                        + weight * their_future,
                    }
                )
        except (ValueError, KeyError) as exc:
            return {**unavailable, "reason": str(exc)}

        def span(key):
            values = [s[key] for s in scenarios]
            return {"low": min(values), "high": max(values)}

        me, partner = span("my_total_change"), span("partner_total_change")
        if me["low"] >= 0 and partner["low"] >= 0:
            verdict = "both_benefit_in_modeled_scenarios"
        elif me["low"] > 0 and partner["high"] < 0:
            verdict = "favors_you_in_modeled_scenarios"
        elif partner["low"] > 0 and me["high"] < 0:
            verdict = "favors_partner_in_modeled_scenarios"
        elif me["high"] < 0 and partner["high"] < 0:
            verdict = "both_lose_in_modeled_scenarios"
        else:
            verdict = "depends_on_assumptions"
        return {
            "status": "conditional_estimate",
            "verdict": verdict,
            "units": "current lineup points plus weighted next-season surplus points",
            "my_total_change": me,
            "partner_total_change": partner,
            "my_future_change": span("my_future_change"),
            "partner_future_change": span("partner_future_change"),
            "scenario_count": len(scenarios),
            "scenarios": scenarios,
            "assumptions": e["assumptions"],
            "acceptance_probability": None,
        }


def fetch_draft_costs(league_id, season, roster, client=None):
    """Read two drafts; preserve unknown original costs rather than inventing them."""
    import requests

    from fantasyfootball.data.sleeper import SleeperClient

    client = client or SleeperClient()
    sid_to_pid = dict(zip(roster.sleeper_id.astype(str), roster.player_id.astype(str)))
    result = {}
    try:
        league = client.get(f"league/{league_id}")
        for offset in range(2):
            drafts = client.get(f"league/{league['league_id']}/drafts")
            matches = [
                d
                for d in drafts
                if str(d.get("season")) == str(season - offset)
                and d.get("status") == "complete"
            ]
            if len(matches) != 1:
                break
            for pick in client.get(f"draft/{matches[0]['draft_id']}/picks"):
                pid = sid_to_pid.get(str(pick["player_id"]))
                if pid is None:
                    continue
                if offset == 0:
                    result[pid] = {
                        "latest_round": int(pick["round"]),
                        "consecutive_keeps": int(bool(pick.get("is_keeper"))),
                    }
                    if not pick.get("is_keeper"):
                        result[pid]["original_round"] = int(pick["round"])
                elif pid in result and result[pid]["consecutive_keeps"]:
                    if pick.get("is_keeper"):
                        result[pid]["consecutive_keeps"] += 1
                    else:
                        result[pid]["original_round"] = int(pick["round"])
            previous = league.get("previous_league_id")
            if not previous:
                break
            league = client.get(f"league/{previous}")
    except (requests.RequestException, KeyError, ValueError, TypeError):
        # Unknown records remain explicit sensitivity inputs; no zero-cost keepers.
        pass
    return result
