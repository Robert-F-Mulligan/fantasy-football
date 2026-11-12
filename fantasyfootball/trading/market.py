"""External market evidence kept separate from roster value and keeper rights."""

import math
from datetime import datetime, timezone


class FantasyCalcMarket:
    URL = "https://api.fantasycalc.com/values/current"

    def fetch(self, report, roster, *, session=None, now=None):
        import requests

        now = now or datetime.now(timezone.utc)
        settings = report.get("waiver_settings", {})
        positions = report.get("roster_positions", [])
        qbs = positions.count("QB") + positions.count("SUPER_FLEX")
        teams = settings.get("num_teams")
        ppr = report.get("scoring_settings", {}).get("rec", 0)
        snapshot = {
            "source": "FantasyCalc",
            "source_url": "https://fantasycalc.com/frequently-asked-questions",
            "fetched_at": now.isoformat(),
            "status": "unavailable",
            "quotes": {},
            "league_type": settings.get("type"),
            "keeper_limit": settings.get("max_keepers"),
            "format": {"mode": "redraft", "teams": teams, "qbs": qbs, "ppr": ppr},
            "limits": [
                "Raw market sums do not adjust for multi-player consolidation",
                "Provider parameters do not match all custom scoring rules",
                "Keeper rights and future draft picks are excluded",
                "Fetch time is not the provider's publication timestamp",
            ],
        }
        if (
            teams not in {8, 10, 12, 14, 16}
            or qbs not in {1, 2}
            or ppr not in {0, 0.5, 1}
        ):
            snapshot["reason"] = (
                "Unsupported market format; no silent scoring approximation"
            )
            return snapshot
        try:
            response = (session or requests).get(
                self.URL,
                params={
                    "isDynasty": "false",
                    "numQbs": qbs,
                    "numTeams": teams,
                    "ppr": ppr,
                },
                timeout=(10, 30),
            )
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list) or not rows:
                raise ValueError("Empty market response")
            by_sleeper = {}
            ambiguous = set()
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("player"), dict):
                    raise TypeError("Malformed market player")
                player = row["player"]
                sid = player.get("sleeperId")
                if sid is None:
                    continue
                sid = str(sid)
                value = float(row["value"])
                if not math.isfinite(value) or value < 0:
                    raise ValueError("Invalid market value")
                if sid in by_sleeper:
                    ambiguous.add(sid)
                by_sleeper[sid] = {
                    "value": value,
                    "provider_name": player["name"],
                    "position": player["position"],
                }
            for row in roster.itertuples():
                sid = str(row.sleeper_id)
                quote = by_sleeper.get(sid)
                if quote and sid not in ambiguous and quote["position"] == row.pos:
                    snapshot["quotes"][str(row.player_id)] = {
                        **quote,
                        "sleeper_id": sid,
                    }
            if not snapshot["quotes"]:
                raise ValueError("No exact-ID market matches")
            snapshot["status"] = "available"
        except (requests.RequestException, ValueError, KeyError, TypeError):
            snapshot["quotes"] = {}
            snapshot["reason"] = (
                "Market feed unavailable or invalid; no fairness verdict"
            )
        return snapshot


class FairnessAssessment:
    def __init__(self, snapshot, *, now=None, max_age_hours=24):
        self.snapshot = snapshot
        self.now = now or datetime.now(timezone.utc)
        self.max_age_hours = max_age_hours

    def assess(self, give, receive, give_picks=(), receive_picks=()):
        result = {
            "verdict": "not_established",
            "acceptance_probability": None,
            "source": self.snapshot.get("source"),
            "source_url": self.snapshot.get("source_url"),
            "fetched_at": self.snapshot.get("fetched_at"),
            "player_market_comparison": None,
            "limits": self.snapshot.get("limits", []),
        }
        if self.snapshot.get("status") != "available":
            return {
                **result,
                "status": "unavailable",
                "reason": self.snapshot.get("reason", "Market data unavailable"),
            }
        try:
            age = (
                self.now - datetime.fromisoformat(self.snapshot["fetched_at"])
            ).total_seconds() / 3600
            if not 0 <= age <= self.max_age_hours:
                raise ValueError("Stale market snapshot")
        except (ValueError, TypeError, KeyError):
            return {
                **result,
                "status": "stale",
                "reason": "Refresh market prices before assessing the offer",
            }
        if give_picks or receive_picks:
            return {
                **result,
                "status": "unpriced_future_picks",
                "reason": "Future all-player/keeper draft picks have no comparable market price; dynasty rookie-pick values and rank indices cannot substitute",
            }
        missing = [
            pid
            for pid in list(give) + list(receive)
            if pid not in self.snapshot["quotes"]
        ]
        if missing:
            return {
                **result,
                "status": "incomplete_prices",
                "missing_player_ids": missing,
                "reason": "One or more players have no exact-ID price; missing is not zero",
            }
        sent = sum(self.snapshot["quotes"][pid]["value"] for pid in give)
        received = sum(self.snapshot["quotes"][pid]["value"] for pid in receive)
        gap = received - sent
        denominator = (sent + received) / 2
        comparison = {
            "give_total": sent,
            "receive_total": received,
            "receive_minus_give": gap,
            "symmetric_gap_percent": 100 * gap / denominator if denominator else None,
            "direction": "higher quoted value received"
            if gap > 0
            else "higher quoted value sent"
            if gap < 0
            else "equal quoted values",
            "units": "FantasyCalc redraft market units, not fantasy points",
        }
        status = (
            "keeper_unresolved"
            if self.snapshot.get("league_type") in {1, 2}
            else "market_reference_only"
        )
        return {
            **result,
            "status": status,
            "player_market_comparison": comparison,
            "reason": "Keeper rights and future pick costs are not valued"
            if status == "keeper_unresolved"
            else "Market gap is evidence, not a calibrated fair/unfair or acceptance forecast",
        }
