import pytest
from test_data_sync import sources

from fantasyfootball.data.registry import PlayerRegistry
from fantasyfootball.data.sleeper import SleeperLeagueImporter


class Client:
    def __init__(self):
        self.league = {
            "name": "Test",
            "sport": "nfl",
            "season": "2026",
            "total_rosters": 12,
            "roster_positions": ["QB", "RB", "FLEX", "K", "DEF", "BN"],
            "scoring_settings": {
                "pass_td": 6,
                "pass_int": -1,
                "rec": 1,
                "st_ff": 1,
                "xpm": 1,
            },
        }
        self.users = [
            {
                "user_id": "u",
                "display_name": "owner",
                "metadata": {"team_name": "Test Team"},
            }
        ]
        self.rosters = [
            {
                "owner_id": "u",
                "roster_id": 1,
                "players": ["003", "004", "PIT"],
                "starters": ["003", "004", "0", "0", "PIT"],
            }
        ]

    def get(self, path):
        if path.endswith("/users"):
            return self.users
        if path.endswith("/rosters"):
            return self.rosters
        return self.league


def setup():
    players, roster, _ = sources()
    client = Client()
    return client, SleeperLeagueImporter(client), PlayerRegistry(players, roster)


def test_import_preserves_scoring_gaps_and_identity():
    _, importer, registry = setup()
    bundle = importer.fetch("123", 2026, "test team", registry)
    assert bundle["league"]["scoring"]["passing_td"] == 6
    assert bundle["league"]["scoring"]["passing_int"] == -1
    assert bundle["report"]["unsupported_offensive_scoring"] == {"st_ff": 1}
    assert not bundle["report"]["exact_offensive_scoring_supported"]
    assert bundle["report"]["unmatched_roster_ids"] == ["PIT"]
    assert len(bundle["my_roster"]) == 3
    assert bundle["my_roster"].player_id.iloc[:2].tolist() == ["00-001", "00-002"]
    assert bundle["slots"]["DEF1"] == ["DEF"]
    assert "DEF1" not in bundle["offensive_slots"]


@pytest.mark.parametrize(
    "kind", ["season", "team", "duplicate_owner", "duplicate_player"]
)
def test_bad_league_context_rejected(kind):
    client, importer, registry = setup()
    if kind == "season":
        client.league["season"] = "2025"
    if kind == "team":
        client.users = []
    if kind == "duplicate_owner":
        client.rosters.append(dict(client.rosters[0], roster_id=2))
    if kind == "duplicate_player":
        client.rosters.append(dict(client.rosters[0], owner_id="other", roster_id=2))
    with pytest.raises(ValueError):
        importer.fetch("123", 2026, "Test Team", registry)


def test_save_does_not_overwrite_and_retains_audit(tmp_path):
    _, importer, registry = setup()
    bundle = importer.fetch("123", 2026, "Test Team", registry)
    path = importer.save(bundle, tmp_path / "import")
    assert (path / "import-report.json").exists()
    assert (path / "league-supported-offense.json").exists()
    with pytest.raises(FileExistsError):
        importer.save(bundle, path)


def test_superflex_uses_explicit_slots_without_wrong_draft_config(tmp_path):
    client, importer, registry = setup()
    client.league["roster_positions"].append("SUPER_FLEX")
    client.rosters[0]["starters"].append("0")
    bundle = importer.fetch("123", 2026, "Test Team", registry)
    assert bundle["offensive_slots"]["SUPER_FLEX1"] == ["QB", "RB", "WR", "TE"]
    path = importer.save(bundle, tmp_path / "import")
    assert not (path / "league-supported-offense.json").exists()
