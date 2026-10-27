"""Adapters for provider-specific data at the application boundary."""

from fantasyfootball.core.domain import ScoringRules, numeric, players


class WeeklyHistoryAdapter:
    """Convert PFR-style weekly rows to one scored player-season record.

    Stable player_id is required. Explicit stat zeros must be supplied before
    scoring. Restrict rows to regular-season games before calling this adapter.
    """

    def __init__(self, scoring=None):
        self.scoring = scoring or ScoringRules()

    def transform(self, weekly):
        data = (
            weekly.rename(columns={"year": "season"}).copy()
            if "season" not in weekly
            else weekly.copy()
        )
        data = numeric(players(data), ["season", "week"])
        if data.duplicated(["player_id", "season", "week"]).any():
            raise ValueError("Duplicate player-season-week rows")
        if ((data.season % 1 != 0) | (data.week % 1 != 0) | (data.week < 1)).any():
            raise ValueError("Season and week must be integers; week must be positive")
        data["fantasy_points"] = self.scoring.score(data)
        data = data.sort_values(["season", "week"])
        return data.groupby(["player_id", "season"], as_index=False).agg(
            player_name=("player_name", "last"),
            pos=("pos", "last"),
            games=("week", "size"),
            fantasy_points=("fantasy_points", "sum"),
        )


class FantasyProsProjectionAdapter:
    """Normalize FantasyPros stat names without assuming its scoring rules.

    The provider's projected_fantasy_points is retained for comparison, never
    promoted to projected_points. DraftApplication scores the normalized stats
    using the requested league unless the caller supplies projected_points.
    """

    STAT_ALIASES = {
        "passing_tds": "passing_td",
        "passing_ints": "passing_int",
        "rushing_tds": "rushing_td",
        "receiving_tds": "receiving_td",
    }

    def transform(self, projections):
        if projections.columns.has_duplicates:
            raise ValueError("Projection columns must be unique")
        for source, target in self.STAT_ALIASES.items():
            if source in projections and target in projections:
                raise ValueError(f"Ambiguous projection columns: {source} and {target}")
        return projections.rename(columns=self.STAT_ALIASES).copy()
