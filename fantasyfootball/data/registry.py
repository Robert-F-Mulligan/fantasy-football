"""Explicit provider-ID reconciliation; never matches players by display name."""

from typing import ClassVar

import pandas as pd


class PlayerRegistry:
    PROVIDERS: ClassVar[dict[str, str]] = {
        "pfr_id": "pfr",
        "espn_id": "espn",
        "sleeper_id": "sleeper",
        "yahoo_id": "yahoo",
    }

    def __init__(self, players, rosters):
        required = {"gsis_id", "display_name", "position"}
        if not required.issubset(players):
            raise ValueError(f"Player registry requires {sorted(required)}")
        if (
            players.empty
            or players.gsis_id.isna().any()
            or players.gsis_id.duplicated().any()
        ):
            raise ValueError("Player registry requires unique nonmissing GSIS IDs")
        self.players = players.rename(
            columns={
                "gsis_id": "player_id",
                "display_name": "player_name",
                "position": "pos",
            }
        ).copy()
        self.players["player_id"] = self.players.player_id.astype(str).str.strip()
        if (
            self.players.player_id.eq("").any()
            or self.players.player_id.duplicated().any()
        ):
            raise ValueError("Blank or duplicate canonical IDs")
        if "gsis_id" not in rosters:
            raise ValueError("Roster requires gsis_id")
        rosters = rosters.copy()
        rosters["gsis_id"] = (
            rosters.gsis_id.astype("string").str.strip().replace("", pd.NA)
        )
        valid_rosters = rosters.loc[rosters.gsis_id.notna()].copy()
        missing = set(valid_rosters.gsis_id.astype(str)) - set(self.players.player_id)
        self.players["registry_source"] = "players"
        if missing:
            if not {"full_name", "position"}.issubset(valid_rosters):
                raise ValueError("Roster-only players require full_name and position")
            additions = valid_rosters.loc[
                valid_rosters.gsis_id.isin(missing),
                ["gsis_id", "full_name", "position"],
            ].drop_duplicates()
            if additions.gsis_id.duplicated().any() or additions.isna().any().any():
                raise ValueError(
                    "Conflicting or incomplete roster-only player identity"
                )
            additions = additions.rename(
                columns={
                    "gsis_id": "player_id",
                    "full_name": "player_name",
                    "position": "pos",
                }
            )
            additions["registry_source"] = "rosters"
            self.players = pd.concat([self.players, additions], ignore_index=True)
        self.unidentified_rosters = rosters.loc[rosters.gsis_id.isna()].copy()
        self.rosters = valid_rosters.rename(columns={"gsis_id": "player_id"}).copy()
        records = []
        for frame in [players, valid_rosters]:
            for column, provider in {"gsis_id": "gsis", **self.PROVIDERS}.items():
                if column not in frame:
                    continue
                for canonical, external in zip(frame.gsis_id, frame[column]):
                    if pd.isna(external) or not str(external).strip():
                        continue
                    records.append(
                        {
                            "provider": provider,
                            "external_id": str(external).strip(),
                            "player_id": str(canonical).strip(),
                        }
                    )
        self.aliases = pd.DataFrame(records).drop_duplicates().reset_index(drop=True)
        duplicate = self.aliases.duplicated(["provider", "external_id"], keep=False)
        self.conflicts = self.aliases.loc[duplicate].copy()
        self.aliases = self.aliases.loc[~duplicate].copy()

    def resolve(self, frame, provider, id_column="player_id", strict=True):
        if provider not in {"gsis", *self.PROVIDERS.values()}:
            raise ValueError(f"Unsupported ID provider: {provider}")
        if id_column not in frame:
            raise ValueError(f"Missing ID column: {id_column}")
        result = frame.copy()
        ids = result[id_column].astype("string").str.strip()
        mapping = (
            self.aliases[self.aliases.provider == provider]
            .set_index("external_id")
            .player_id
        )
        mapped = ids.map(mapping)
        conflicted = set(
            self.conflicts.loc[self.conflicts.provider == provider, "external_id"]
        )
        result["id_match_status"] = "matched"
        result.loc[mapped.isna(), "id_match_status"] = "unmatched"
        result.loc[ids.isin(conflicted), "id_match_status"] = "ambiguous"
        if strict and mapped.isna().any():
            raise ValueError(
                f"{int(mapped.isna().sum())} {provider} IDs are unmatched or ambiguous"
            )
        result["source_player_id"] = ids
        result["player_id"] = mapped
        return result
