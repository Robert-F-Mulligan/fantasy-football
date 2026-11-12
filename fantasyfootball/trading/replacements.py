"""Use the same canonical ownership rules as waiver recommendations."""

from fantasyfootball.data.sleeper import load_registry
from fantasyfootball.waivers.service import candidates


def replacement_pool(args, details, rosters, imported, history):
    pool = candidates(
        load_registry(args.input.parent),
        details,
        rosters,
        imported.get("owned_sleeper_ids", []),
    )
    counts = history.groupby("player_id").size()
    return pool.loc[
        pool.pos.isin(["QB", "RB", "WR", "TE"]) & pool.player_id.map(counts).ge(4)
    ].copy()
