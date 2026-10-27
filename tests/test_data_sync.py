from hashlib import sha256

import pandas as pd
import pytest

from fantasyfootball.data.data_sync import DataSyncService, PlayerStatsAdapter
from fantasyfootball.forecasting.features import prepare_weekly
from fantasyfootball.data.registry import PlayerRegistry


def sources():
    players = pd.DataFrame(
        [
            {
                "gsis_id": "00-001",
                "display_name": "Same Name",
                "position": "QB",
                "espn_id": "012",
            }
        ]
    )
    roster = pd.DataFrame(
        [
            {
                "gsis_id": "00-001",
                "full_name": "Same Name",
                "position": "QB",
                "season": "2026",
                "sleeper_id": "003",
            },
            {
                "gsis_id": "00-002",
                "full_name": "Same Name",
                "position": "WR",
                "season": "2026",
                "sleeper_id": "004",
            },
        ]
    )
    stats = dict.fromkeys(PlayerStatsAdapter.COLUMNS, "0")
    stats.update(
        player_id="00-001",
        player_name="S.Name",
        player_display_name="Same Name",
        position="QB",
        opponent_team="BUF",
        team="NYJ",
        season="2026",
        week="7",
        season_type="REG",
        passing_yards="250",
        passing_tds="2",
    )
    return players, roster, pd.DataFrame([stats])


class FakeClient:
    def __init__(self):
        self.players, self.roster, self.stats = sources()

    def csv(self, tag, filename):
        frame = {
            "players": self.players,
            "rosters": self.roster,
            "stats_player": self.stats,
        }[tag]
        return frame.copy(), {
            "sha256": sha256(frame.to_csv(index=False).encode()).hexdigest(),
            "url": filename,
        }


def test_registry_explicit_ids_and_roster_only_players():
    players, roster, _ = sources()
    registry = PlayerRegistry(players, roster)
    assert registry.players.player_id.tolist() == ["00-001", "00-002"]
    assert registry.players.registry_source.tolist() == ["players", "rosters"]
    assert registry.resolve(
        pd.DataFrame({"player_id": ["004"]}), "sleeper"
    ).player_id.tolist() == ["00-002"]
    assert registry.resolve(
        pd.DataFrame({"player_id": ["012"]}), "espn"
    ).player_id.tolist() == ["00-001"]
    assert "registry_source" not in players
    with pytest.raises(ValueError, match="unmatched"):
        registry.resolve(pd.DataFrame({"player_id": ["Same Name"]}), "gsis")


def test_ambiguous_ids_are_quarantined():
    players, roster, _ = sources()
    roster["sleeper_id"] = "003"
    registry = PlayerRegistry(players, roster)
    result = registry.resolve(
        pd.DataFrame({"player_id": ["003", "999"]}), "sleeper", strict=False
    )
    assert result.id_match_status.tolist() == ["ambiguous", "unmatched"]
    assert result.player_id.isna().all()
    with pytest.raises(ValueError, match="ambiguous"):
        registry.resolve(pd.DataFrame({"player_id": ["003"]}), "sleeper")


@pytest.mark.parametrize("kind", ["empty", "duplicate", "blank"])
def test_invalid_registry(kind):
    players, roster, _ = sources()
    if kind == "empty":
        players = players.iloc[:0]
    if kind == "duplicate":
        players = pd.concat([players, players])
    if kind == "blank":
        players.loc[0, "gsis_id"] = " "
    with pytest.raises(ValueError):
        PlayerRegistry(players, roster)


def test_stats_are_model_ready_and_league_scored():
    players, roster, raw = sources()
    adapted = PlayerStatsAdapter().transform(raw, PlayerRegistry(players, roster), 2026)
    assert prepare_weekly(adapted).fantasy_points.tolist() == [18.0]
    assert adapted.player_name.tolist() == ["Same Name"]
    assert "fantasy_points" not in adapted
    with pytest.raises(ValueError, match="Duplicate"):
        PlayerStatsAdapter().transform(
            pd.concat([raw, raw]), PlayerRegistry(players, roster), 2026
        )


def test_sync_is_idempotent_and_detects_corruption(tmp_path):
    service = DataSyncService(FakeClient())
    first, report = service.sync([2026], 2026, tmp_path, 7)
    assert service.sync([2026], 2026, tmp_path, 7)[0] == first
    assert len(list((tmp_path / "snapshots").iterdir())) == 1
    assert report["coverage"][0]["complete_schedule_verified"] is False
    pointer = (tmp_path / "current.json").read_bytes()
    (first / "weekly.csv").write_text("corrupt")
    with pytest.raises(ValueError, match="corrupt"):
        service.sync([2026], 2026, tmp_path)
    assert (tmp_path / "current.json").read_bytes() == pointer


def test_manifest_corruption_rejected(tmp_path):
    service = DataSyncService(FakeClient())
    snapshot, _ = service.sync([2026], 2026, tmp_path)
    (snapshot / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        service.sync([2026], 2026, tmp_path)


def test_failed_refresh_preserves_current(tmp_path):
    client = FakeClient()
    service = DataSyncService(client)
    service.sync([2026], 2026, tmp_path)
    pointer = (tmp_path / "current.json").read_bytes()
    with pytest.raises(ValueError, match="below required"):
        service.sync([2026], 2026, tmp_path, 8)
    client.stats.loc[0, "player_id"] = "unknown"
    with pytest.raises(ValueError, match="unmatched"):
        service.sync([2026], 2026, tmp_path)
    assert (tmp_path / "current.json").read_bytes() == pointer


def test_optional_scoring_stats_survive_adapter():
    players, roster, raw = sources()
    raw["passing_2pt_conversions"] = "1"
    raw["special_teams_tds"] = "2"
    frame = PlayerStatsAdapter().transform(raw, PlayerRegistry(players, roster), 2026)
    assert frame.passing_2pt_conversions.tolist() == ["1"]
    assert frame.special_teams_tds.tolist() == ["2"]
