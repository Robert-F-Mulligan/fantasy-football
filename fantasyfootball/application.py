"""CSV-first application service; sources, models and charts remain replaceable."""

from .adapters import FantasyProsProjectionAdapter
from .domain import LeagueSettings, ScoringRules, players
from .drafting import DraftService
from .projections import WeightedHistoryModel


class DraftApplication:
    def __init__(self, league=None, model=None, projection_adapter=None):
        self.league = league or LeagueSettings()
        self.model = model or WeightedHistoryModel()
        self.drafts = DraftService(self.league)
        self.projection_adapter = projection_adapter or FantasyProsProjectionAdapter()

    def prepare(self, data, *, season=None, adp=None, **draft_options):
        if season is not None:
            projections = self.model.predict(data, season)
        else:
            projections = players(self.projection_adapter.transform(data))
            if "projected_points" not in projections:
                projections["projected_points"] = self.league.scoring.score(projections)
        if adp is not None:
            market = adp.copy()
            if "player_id" not in market or "adp" not in market:
                raise ValueError("ADP data requires player_id and adp")
            if market.player_id.isna().any():
                raise ValueError("ADP player_id cannot be blank")
            market["player_id"] = market.player_id.astype(str).str.strip()
            if market.player_id.eq("").any() or market.player_id.duplicated().any():
                raise ValueError("ADP player IDs must be nonempty and unique")
            cols = ["player_id", "adp"] + (["adp_std"] if "adp_std" in market else [])
            projections = projections.drop(
                columns=["adp", "adp_std"], errors="ignore"
            ).merge(market[cols], on="player_id", how="left", validate="one_to_one")
        return self.drafts.rank(projections, **draft_options)


def league_from_dict(data):
    if "team_n" in data:
        return LeagueSettings.from_legacy(data)
    config = dict(data)
    if "scoring" in config:
        config["scoring"] = ScoringRules(config["scoring"])
    return LeagueSettings(**config)
