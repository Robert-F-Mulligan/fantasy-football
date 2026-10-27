"""Available-player rankings with explicit, uncalibrated FAAB spending ranges."""

import json
import math

import pandas as pd

from fantasyfootball.data.sleeper import load_registry
from fantasyfootball.forecasting.specialists import specialist_context
from fantasyfootball.lineups.weekly import WeeklyLineupPlanner


class FaabPolicy:
    """Percent of original budget, capped by observed remaining funds; not auction prices."""

    def __init__(self, report):
        settings = report.get("waiver_settings", {})
        self.total = settings.get("waiver_budget")
        self.used = report.get("waiver_budget_used")
        self.minimum = settings.get("waiver_bid_min")
        self.remaining = None
        values = [self.total, self.used, self.minimum]
        if (
            settings.get("waiver_type") == 2
            and all(
                isinstance(v, (int, float))
                and not isinstance(v, bool)
                and math.isfinite(v)
                and v == int(v)
                for v in values
            )
            and self.total > 0
            and 0 <= self.used <= self.total
            and self.minimum >= 0
        ):
            self.remaining = int(self.total - self.used)

    def recommend(self, gain, *, kicker=False, uncertain=False):
        if self.remaining is None or pd.isna(gain):
            return None, None, "Budget or roster comparison unavailable"
        low, high = (
            (0, 1)
            if gain <= 0
            else ((1, 3) if gain < 2 else ((3, 7) if gain < 5 else (7, 15)))
        )
        if kicker or uncertain:
            low, high = min(low, 1), min(high, 3)
        if self.remaining < self.minimum:
            return None, None, "Remaining balance below minimum bid"
        return (
            min(
                self.remaining,
                max(int(self.minimum), math.floor(self.total * low / 100)),
            ),
            min(
                self.remaining,
                max(int(self.minimum), math.ceil(self.total * high / 100)),
            ),
            "Heuristic spending range; one-week value, not a winning-bid estimate",
        )


def candidates(registry, details, rosters, extra_owned=()):
    """Ownership is excluded by both provider and canonical ID, before modeling."""
    if rosters.sleeper_id.isna().any() or rosters.sleeper_id.duplicated().any():
        raise ValueError("Invalid league ownership snapshot")
    owned = set(rosters.sleeper_id.astype(str)) | {str(p) for p in extra_owned}
    owned_canonical = set(rosters.player_id.dropna().astype(str))
    aliases = registry.aliases.loc[registry.aliases.provider.eq("sleeper")]
    mapping = aliases.set_index("external_id").player_id.to_dict()
    rows = []
    for sid, info in details.items():
        sid = str(sid)
        pos = info.get("position")
        pid = mapping.get(sid)
        if (
            sid in owned
            or pid in owned_canonical
            or pos not in {"QB", "RB", "WR", "TE", "K", "DEF"}
        ):
            continue
        rows.append(
            {
                "sleeper_id": sid,
                "player_id": pid,
                "player_name": info.get("full_name") or sid,
                "pos": pos,
                "starter_slot": "",
                "is_reserve": False,
                "is_taxi": False,
            }
        )
    columns = [
        "sleeper_id",
        "player_id",
        "player_name",
        "pos",
        "starter_slot",
        "is_reserve",
        "is_taxi",
    ]
    result = pd.DataFrame(rows, columns=columns)
    duplicate = result.player_id.notna() & result.player_id.duplicated(keep=False)
    return result.loc[~duplicate].copy()


def write_waivers(
    args, history, model, ranges, availability, projections, report, slots
):
    source = args.league_dir / "rosters.csv"
    if not source.exists():
        return {
            "status": "unavailable",
            "reason": "League-wide ownership snapshot missing",
        }
    details = json.loads(args.players.read_text(encoding="utf-8-sig"))
    rosters = pd.read_csv(source, dtype={"sleeper_id": str, "player_id": str})
    pool = candidates(
        load_registry(args.input.parent),
        details,
        rosters,
        report.get("owned_sleeper_ids", []),
    )
    policy = FaabPolicy(report)
    metadata = {
        "status": "ready",
        "remaining_faab": policy.remaining,
        "original_budget": policy.total,
        "as_of": args.as_of,
        "limits": "Unrostered is not a guarantee of claim eligibility. Check pending claims, drop locks and waiver deadlines in Sleeper. FAAB ranges are independent alternatives, not a combined spending plan. One-week research; no rest-of-season valuation or bidding-market model. Defense is unranked.",
    }
    planner = WeeklyLineupPlanner()
    schedule = pd.read_csv(args.schedule)
    context = planner.availability(
        pool, details, schedule, season=args.season, week=args.week, as_of=args.as_of
    )
    context.to_csv(args.output / "waiver-availability.csv", index=False)
    eligible = context.loc[
        context.availability.eq("eligible") & context.pos.isin(["QB", "RB", "WR", "TE"])
    ].copy()
    board = pd.DataFrame()
    if not eligible.empty:
        fixtures = eligible[
            ["player_id", "player_name", "pos", "season", "week", "opp"]
        ]
        board = ranges.apply(model.predict(fixtures=fixtures))
        board = board.merge(
            eligible[["player_id", "sleeper_id", "warning", "kickoff"]],
            on="player_id",
            validate="one_to_one",
        )
    base = None
    try:
        base = float(
            planner.recommend(projections, availability, slots).projected_points.sum()
        )
    except ValueError:
        metadata["lineup_comparison"] = (
            "Unavailable: current offensive lineup incomplete"
        )
    records = []
    for row in board.to_dict("records"):
        gain = float("nan")
        if base is not None:
            added = context.loc[context.player_id.eq(row["player_id"])]
            proposed = pd.concat([availability, added], ignore_index=True)
            projected = pd.concat([projections, pd.DataFrame([row])], ignore_index=True)
            gain = max(
                0.0,
                float(
                    planner.recommend(projected, proposed, slots).projected_points.sum()
                )
                - base,
            )
        row["warning"] = (
            row.get("warning") or ""
        ) + " Current depth-chart role unverified."
        if row["history_games"] < 4:
            row["warning"] += " Fewer than four historical games; weak forecast."
        row["lineup_gain"] = gain
        low, high, note = policy.recommend(
            gain,
            uncertain="Injury designation" in row["warning"]
            or row["history_games"] < 4,
        )
        row.update(
            faab_low=low,
            faab_high=high,
            bid_note=note,
            model_note="Offensive model",
            rank=None,
        )
        records.append(row)
    raw_path = args.input.parent / "kickers.csv"
    spec, _spec_audit = specialist_context(
        pool,
        details,
        schedule,
        pd.read_csv(raw_path, dtype={"player_id": str}) if raw_path.exists() else None,
        report["scoring_settings"],
        season=args.season,
        week=args.week,
        as_of=args.as_of,
        kicker_slots=0,
    )
    own_path = args.output / "specialists.csv"
    own = pd.read_csv(own_path) if own_path.exists() else pd.DataFrame()
    for row in (
        spec.loc[spec.availability.eq("eligible")].to_dict("records")
        if not spec.empty
        else []
    ):
        gain = float("nan")
        # K comparisons only for the supported single-K league and a known unlocked baseline.
        if (
            row["pos"] == "K"
            and report["roster_positions"].count("K") == 1
            and not own.empty
        ):
            ks = own.loc[own.pos.eq("K")]
            valid = ks.loc[ks.availability.eq("eligible")]
            if (
                not ks.availability.isin(["unknown", "locked_starter"]).any()
                and not valid.empty
                and valid.projected_points.notna().all()
                and pd.notna(row["projected_points"])
            ):
                gain = max(0.0, row["projected_points"] - valid.projected_points.max())
        coverage_need = (
            row["pos"] == "K"
            and pd.notna(row["projected_points"])
            and report["roster_positions"].count("K") == 1
            and not own.empty
            and len(own.loc[own.pos.eq("K")]) == 1
            and own.loc[own.pos.eq("K"), "availability"].eq("no_scheduled_game").all()
        )
        low, high, note = policy.recommend(
            1.0 if coverage_need else gain,
            kicker=True,
            uncertain=bool(row.get("warning")),
        )
        if coverage_need:
            row["warning"] = (
                "Rostered kicker has no scheduled game; coverage bid, not a measured lineup gain."
            )
        row.update(
            lineup_gain=gain, faab_low=low, faab_high=high, bid_note=note, rank=None
        )
        records.append(row)
    rankings = pd.DataFrame(records)
    categories = {p: [p] for p in ["QB", "RB", "WR", "TE", "K", "DEF"]}
    for slot, positions in slots.items():
        if len(positions) > 1:
            categories[slot.rstrip("0123456789")] = positions
    output = []
    for category, positions in categories.items():
        if rankings.empty:
            continue
        subset = (
            rankings.loc[rankings.pos.isin(positions)]
            .sort_values(
                ["projected_points", "player_name"],
                ascending=[False, True],
                na_position="last",
            )
            .copy()
        )
        subset["category"] = category
        subset["rank"] = range(1, len(subset) + 1)
        subset.loc[subset.projected_points.isna(), "rank"] = None
        output.append(subset.head(5))
    columns = [
        "category",
        "rank",
        "player_id",
        "sleeper_id",
        "player_name",
        "pos",
        "opp",
        "projected_points",
        "lineup_gain",
        "faab_low",
        "faab_high",
        "warning",
        "bid_note",
        "model_note",
    ]
    result = (
        pd.concat(output, ignore_index=True)
        if output
        else pd.DataFrame(columns=columns)
    )
    result.to_csv(args.output / "waivers.csv", index=False)
    metadata["categories"] = list(categories)
    metadata["unranked_offensive_candidates"] = int(
        (
            context.pos.isin(["QB", "RB", "WR", "TE"])
            & ~context.availability.eq("eligible")
        ).sum()
    )
    metadata["lineup_gain_note"] = (
        "Gain from adding one player to the optimized roster, including FLEX and kickoff locks. Conditional on an open roster spot or a safe bench drop; not drop advice."
    )
    (args.output / "waiver-report.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata
