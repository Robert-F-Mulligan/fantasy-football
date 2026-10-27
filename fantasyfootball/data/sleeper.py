"""Read-only Sleeper league import with explicit scoring and identity coverage."""

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import pandas as pd
import requests

from fantasyfootball.data.registry import PlayerRegistry


class SleeperClient:
    BASE = "https://api.sleeper.app/v1"

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def get(self, path):
        response = self.session.get(f"{self.BASE}/{path}", timeout=(10, 30))
        response.raise_for_status()
        return response.json()


class SleeperLeagueImporter:
    SCORING: ClassVar[dict[str, str]] = {
        "pass_yd": "passing_yds",
        "pass_td": "passing_td",
        "pass_int": "passing_int",
        "rush_yd": "rushing_yds",
        "rush_td": "rushing_td",
        "rec": "receiving_rec",
        "rec_yd": "receiving_yds",
        "rec_td": "receiving_td",
        "fum_lost": "fumbles_lost",
        "fum": "fumbles",
        "pass_2pt": "passing_2pt_conversions",
        "rush_2pt": "rushing_2pt_conversions",
        "rec_2pt": "receiving_2pt_conversions",
        "st_td": "special_teams_tds",
        "fum_rec_td": "fumble_recovery_tds",
    }
    # These settings apply to K, team defense, or IDP; preserve them in the audit.
    NON_OFFENSE: ClassVar[set[str]] = {
        "sack",
        "int",
        "ff",
        "fum_rec",
        "safe",
        "blk_kick",
        "tkl_loss",
        "def_td",
        "xpm",
        "xpmiss",
        "fgmiss",
    }
    ELIGIBILITY: ClassVar[dict[str, list[str]]] = {
        "QB": ["QB"],
        "RB": ["RB"],
        "WR": ["WR"],
        "TE": ["TE"],
        "K": ["K"],
        "DEF": ["DEF"],
        "FLEX": ["RB", "WR", "TE"],
        "SUPER_FLEX": ["QB", "RB", "WR", "TE"],
        "REC_FLEX": ["WR", "TE"],
        "WRRB_FLEX": ["WR", "RB"],
    }

    def __init__(self, client=None):
        self.client = client or SleeperClient()

    def fetch(self, league_id, season, team_name, registry):
        league_id = str(league_id)
        if not re.fullmatch(r"\d+", league_id):
            raise ValueError("Sleeper league ID must contain digits only")
        league = self.client.get(f"league/{league_id}")
        if (
            not league
            or league.get("sport") != "nfl"
            or str(league.get("season")) != str(season)
        ):
            raise ValueError("Sleeper league sport or season does not match request")
        users = self.client.get(f"league/{league_id}/users")
        matches = [
            u
            for u in users
            if team_name.strip().casefold()
            in {
                str((u.get("metadata") or {}).get("team_name", "")).strip().casefold(),
                str(u.get("display_name", "")).strip().casefold(),
            }
        ]
        if len(matches) != 1:
            raise ValueError("Team name must uniquely identify a league member")
        user = matches[0]
        rosters = self.client.get(f"league/{league_id}/rosters")
        own = [
            r
            for r in rosters
            if r.get("owner_id") == user["user_id"]
            or user["user_id"] in (r.get("co_owners") or [])
        ]
        if len(own) != 1:
            raise ValueError("League member must have exactly one roster")
        own = own[0]
        slot_names = []
        slot_counts = Counter()
        for position in league["roster_positions"]:
            if position in {"BN", "IR", "TAXI"}:
                continue
            slot_counts[position] += 1
            slot_names.append(f"{position}{slot_counts[position]}")
        records = []
        for roster in rosters:
            starters = roster.get("starters") or []
            if len(starters) != len(slot_names) or len(
                [p for p in starters if str(p) != "0"]
            ) != len({p for p in starters if str(p) != "0"}):
                raise ValueError(
                    "Starter list does not match league slots or contains duplicates"
                )
            assigned_slots = {
                str(p): slot for p, slot in zip(starters, slot_names) if str(p) != "0"
            }
            if not set(assigned_slots).issubset(
                {str(p) for p in roster.get("players") or []}
            ):
                raise ValueError("Starter is absent from its roster")
            for external in roster.get("players") or []:
                if str(external) == "0":
                    continue
                records.append(
                    {
                        "sleeper_id": str(external),
                        "roster_id": roster["roster_id"],
                        "is_my_team": roster["roster_id"] == own["roster_id"],
                        "is_starter": external in starters,
                        "starter_slot": assigned_slots.get(str(external), ""),
                        "is_reserve": external in (roster.get("reserve") or []),
                        "is_taxi": external in (roster.get("taxi") or []),
                    }
                )
        frame = pd.DataFrame(
            records,
            columns=[
                "sleeper_id",
                "roster_id",
                "is_my_team",
                "is_starter",
                "starter_slot",
                "is_reserve",
                "is_taxi",
            ],
        )
        if frame.sleeper_id.duplicated().any():
            raise ValueError("A player appears on multiple league rosters")
        resolved = registry.resolve(
            frame, "sleeper", id_column="sleeper_id", strict=False
        )
        resolved = resolved.merge(
            registry.players[["player_id", "player_name", "pos"]],
            on="player_id",
            how="left",
            validate="many_to_one",
        )
        slots = {}
        counts = Counter()
        unknown_slots = []
        for position in league["roster_positions"]:
            if position in {"BN", "IR", "TAXI"}:
                continue
            counts[position] += 1
            if position not in self.ELIGIBILITY:
                unknown_slots.append(position)
                continue
            slots[f"{position}{counts[position]}"] = self.ELIGIBILITY[position]
        weights = {}
        excluded = {}
        unsupported = {}
        for key, value in league["scoring_settings"].items():
            if not value:
                continue
            if key in self.SCORING:
                weights[self.SCORING[key]] = value
            elif key in self.NON_OFFENSE or key.startswith(
                ("fgm_", "fgmiss_", "pts_allow_", "def_")
            ):
                excluded[key] = value
            else:
                unsupported[key] = value
        offensive_slots = {
            k: v for k, v in slots.items() if set(v).issubset({"QB", "RB", "WR", "TE"})
        }
        config = {
            "teams": league["total_rosters"],
            "starters": {p: counts[p] for p in ["QB", "RB", "WR", "TE"]},
            "flex": counts["FLEX"],
            "flex_positions": ["RB", "WR", "TE"],
            "scoring": weights,
        }
        extra_flex = any(counts[p] for p in ["SUPER_FLEX", "REC_FLEX", "WRRB_FLEX"])
        report = {
            "league_id": league_id,
            "league_name": league["name"],
            "season": season,
            "team_name": (user.get("metadata") or {}).get(
                "team_name", user["display_name"]
            ),
            "roster_id": own["roster_id"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_url": f"{SleeperClient.BASE}/league/{league_id}",
            "scoring_settings": league["scoring_settings"],
            "roster_positions": league["roster_positions"],
            "unsupported_offensive_scoring": unsupported,
            "excluded_non_offensive_scoring": excluded,
            "unsupported_slots": unknown_slots,
            "draft_config_supported": not extra_flex and not unknown_slots,
            "exact_offensive_scoring_supported": not unsupported,
            "unmatched_roster_ids": resolved.loc[
                resolved.id_match_status != "matched", "sleeper_id"
            ].tolist(),
            "notes": [
                "Supported-offense configuration omits the scoring categories listed above.",
                "The main optimizer is offense-only. Weekly reports may add separate kicking-only baselines and defense context; defense points remain unmodeled.",
                "Starter slots are preserved; weekly-plan combines them with schedule-based kickoff locks.",
            ],
        }
        return {
            "report": report,
            "league": config,
            "slots": slots,
            "offensive_slots": offensive_slots,
            "rosters": resolved,
            "my_roster": resolved.loc[resolved.is_my_team].copy(),
        }

    def save(self, bundle, destination):
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        for name, key in [
            ("import-report", "report"),
            ("slots", "slots"),
            ("offensive-slots", "offensive_slots"),
        ]:
            (destination / f"{name}.json").write_text(
                json.dumps(bundle[key], indent=2), encoding="utf-8"
            )
        if bundle["report"]["draft_config_supported"]:
            (destination / "league-supported-offense.json").write_text(
                json.dumps(bundle["league"], indent=2), encoding="utf-8"
            )
        for key in ["rosters", "my_roster"]:
            bundle[key].to_csv(destination / f"{key}.csv", index=False)
        return destination


def load_registry(snapshot):
    snapshot = Path(snapshot)
    players = pd.read_csv(snapshot / "players.csv", dtype=str).rename(
        columns={
            "player_id": "gsis_id",
            "player_name": "display_name",
            "pos": "position",
        }
    )
    rosters = pd.read_csv(snapshot / "rosters.csv", dtype=str).rename(
        columns={"player_id": "gsis_id"}
    )
    return PlayerRegistry(players, rosters)
