"""Versioned nflverse data bundles with explicit coverage and source provenance."""

import json
import os
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import pandas as pd
import requests

from fantasyfootball.core.domain import numeric
from fantasyfootball.data.registry import PlayerRegistry


class NflverseClient:
    BASE = "https://github.com/nflverse/nflverse-data/releases/download"

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def csv(self, tag, filename):
        url = f"{self.BASE}/{tag}/{filename}"
        response = self.session.get(url, timeout=(10, 90))
        response.raise_for_status()
        content = response.content
        frame = pd.read_csv(BytesIO(content), dtype=str)
        if frame.empty:
            raise ValueError(f"Empty source: {filename}")
        metadata = {
            "url": url,
            "sha256": sha256(content).hexdigest(),
            "rows": len(frame),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "last_modified": response.headers.get("Last-Modified"),
        }
        return frame, metadata


class PlayerStatsAdapter:
    COLUMNS: ClassVar[dict[str, str]] = {
        "player_display_name": "player_name",
        "position": "pos",
        "opponent_team": "opp",
        "attempts": "passing_att",
        "completions": "passing_cmp",
        "passing_yards": "passing_yds",
        "passing_tds": "passing_td",
        "passing_interceptions": "passing_int",
        "carries": "rushing_att",
        "rushing_yards": "rushing_yds",
        "rushing_tds": "rushing_td",
        "targets": "receiving_tgt",
        "receptions": "receiving_rec",
        "receiving_yards": "receiving_yds",
        "receiving_tds": "receiving_td",
        "fumbles_total": "fumbles",
        "fumbles_lost_total": "fumbles_lost",
    }

    def transform(self, raw, registry, season):
        required = {"player_id", "season", "week", "season_type", "team", *self.COLUMNS}
        if not required.issubset(raw):
            raise ValueError(f"Missing nflverse columns: {sorted(required - set(raw))}")
        data = raw.loc[
            (raw.season_type == "REG") & raw.position.isin(["QB", "RB", "WR", "TE"])
        ].copy()
        # The source also has an abbreviated player_name; use its display name.
        data = data.drop(columns=["player_name"], errors="ignore").rename(
            columns=self.COLUMNS
        )
        data = numeric(
            data,
            [
                "season",
                "week",
                *[
                    v
                    for v in self.COLUMNS.values()
                    if v not in ("player_name", "pos", "opp")
                ],
            ],
        )
        if data.empty or not data.season.eq(season).all():
            raise ValueError("Stats do not cover the requested season")
        if ((data.week % 1 != 0) | ~data.week.between(1, 18)).any():
            raise ValueError("Invalid regular-season week")
        if data.duplicated(["player_id", "season", "week"]).any():
            raise ValueError("Duplicate player-season-week records")
        if data[["player_name", "pos", "opp", "team"]].isna().any().any():
            raise ValueError("Missing stats identity or matchup context")
        data = registry.resolve(data, "gsis")
        # Do not carry provider-scored labels into league-specific modeling.
        columns = [
            "player_id",
            "player_name",
            "pos",
            "season",
            "week",
            "team",
            "opp",
            *[
                v
                for v in self.COLUMNS.values()
                if v not in ("player_name", "pos", "opp")
            ],
        ]
        for column in [
            "passing_2pt_conversions",
            "rushing_2pt_conversions",
            "receiving_2pt_conversions",
            "special_teams_tds",
            "fumble_recovery_tds",
            "receiving_air_yards",
            "target_share",
            "air_yards_share",
        ]:
            if column in data:
                columns.append(column)
        return data[columns].reset_index(drop=True)


class DataSyncService:
    def __init__(self, client=None):
        self.client = client or NflverseClient()

    def sync(self, seasons, roster_season, destination, minimum_week=None):
        seasons = sorted(set(seasons))
        if not seasons or any(not isinstance(s, int) or s < 1999 for s in seasons):
            raise ValueError("Request explicit seasons from 1999 onward")
        if not isinstance(roster_season, int) or roster_season < 1999:
            raise ValueError("Invalid roster season")
        if minimum_week is not None and (
            not isinstance(minimum_week, int) or not 1 <= minimum_week <= 18
        ):
            raise ValueError("minimum_week must be 1 through 18")
        sources = {}
        players, sources["players"] = self.client.csv("players", "players.csv")
        rosters, sources["rosters"] = self.client.csv(
            "rosters", f"roster_{roster_season}.csv"
        )
        if not pd.to_numeric(rosters.season, errors="raise").eq(roster_season).all():
            raise ValueError("Roster does not match requested season")
        registry = PlayerRegistry(players, rosters)
        frames = []
        kickers = []
        coverage = []
        for season in seasons:
            raw, sources[f"stats_{season}"] = self.client.csv(
                "stats_player", f"stats_player_week_{season}.csv"
            )
            # Keep kicking box scores separate from the offensive model contract.
            kickers.append(
                raw.loc[(raw.season_type == "REG") & (raw.position == "K")].copy()
            )
            frame = PlayerStatsAdapter().transform(raw, registry, season)
            maximum = int(frame.week.max())
            if minimum_week is not None and maximum < minimum_week:
                raise ValueError(
                    f"{season} only has stats through week {maximum}, below required {minimum_week}"
                )
            frames.append(frame)
            coverage.append(
                {
                    "season": season,
                    "max_observed_week": maximum,
                    "rows": len(frame),
                    "players": frame.player_id.nunique(),
                    "position_rows": frame.pos.value_counts().to_dict(),
                    "complete_schedule_verified": False,
                }
            )
        weekly = pd.concat(frames, ignore_index=True)
        outputs = {
            "players.csv": registry.players,
            "aliases.csv": registry.aliases,
            "id_conflicts.csv": registry.conflicts,
            "rosters.csv": registry.rosters,
            "unidentified_rosters.csv": registry.unidentified_rosters,
            "weekly.csv": weekly,
            "kickers.csv": pd.concat(kickers, ignore_index=True),
        }
        contents = {
            name: frame.to_csv(index=False).encode("utf-8")
            for name, frame in outputs.items()
        }
        hashes = {
            name: sha256(content).hexdigest() for name, content in contents.items()
        }
        identity = {
            "schema_version": 1,
            "sources": {k: v["sha256"] for k, v in sources.items()},
            "files": hashes,
        }
        version = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
        root = Path(destination)
        snapshots = root / "snapshots"
        snapshots.mkdir(parents=True, exist_ok=True)
        target = snapshots / version
        report = {
            "version": version,
            "schema_version": 1,
            "sources": sources,
            "files": hashes,
            "coverage": coverage,
            "roster_season": roster_season,
            "roster_rows": len(rosters),
            "unidentified_roster_rows": len(registry.unidentified_rosters),
            "ambiguous_alias_rows": len(registry.conflicts),
            "notes": [
                "Observed box scores do not establish complete roster, game, DNP or injury coverage.",
                "Current roster/player metadata must not be used as historical as-of features.",
            ],
        }
        if target.exists():
            try:
                saved = json.loads(
                    (target / "manifest.json").read_text(encoding="utf-8")
                )
                if saved["version"] != version or saved["files"] != hashes:
                    raise ValueError("Existing snapshot manifest is inconsistent")
            except (OSError, KeyError, json.JSONDecodeError) as exc:
                raise ValueError("Existing snapshot manifest is corrupt") from exc
            for name, digest in hashes.items():
                if (
                    not (target / name).exists()
                    or sha256((target / name).read_bytes()).hexdigest() != digest
                ):
                    raise ValueError(
                        "Existing snapshot is corrupt; current pointer was not changed"
                    )
        else:
            staging = snapshots / (".staging-" + uuid4().hex)
            staging.mkdir()
            for name, content in contents.items():
                (staging / name).write_bytes(content)
            (staging / "manifest.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            os.replace(staging, target)
        pointer = root / (".current-" + uuid4().hex + ".json")
        pointer.write_text(
            json.dumps(
                {
                    "version": version,
                    "snapshot": str(Path("snapshots") / version),
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(pointer, root / "current.json")
        return target, report
