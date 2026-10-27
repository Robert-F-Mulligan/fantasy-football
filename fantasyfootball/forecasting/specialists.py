"""Separate kicking-only baseline and unmodeled defense context for weekly reports."""

import math

import pandas as pd

from fantasyfootball.core.domain import numeric

BANDS = {
    "0_19": (0, 19),
    "20_29": (20, 29),
    "30_39": (30, 39),
    "40_49": (40, 49),
    "50_59": (50, 59),
    "60p": (60, 100),
}


def kicking_scores(raw, settings):
    """Sleeper miss penalties include blocked kicks; distance and base weights stack."""
    supported = {"fgm", "fgmiss", "xpm", "xpmiss"} | {
        prefix + band for prefix in ("fgm_", "fgmiss_") for band in BANDS
    }
    unknown = [
        k
        for k, v in settings.items()
        if v and k.startswith(("fg", "xp")) and k not in supported
    ]
    if unknown:
        raise ValueError("Unsupported kicking scoring: " + ", ".join(sorted(unknown)))
    weights = {k: float(v) for k, v in settings.items() if k in supported and v}
    if not all(math.isfinite(v) for v in weights.values()):
        raise ValueError("Kicking weights must be finite")
    columns = [
        "fg_made",
        "fg_missed",
        "fg_blocked",
        "pat_made",
        "pat_missed",
        "pat_blocked",
    ]
    for band in BANDS:
        suffix = band.replace("60p", "60_")
        columns += ["fg_made_" + suffix, "fg_missed_" + suffix]
    data = numeric(raw, columns)
    if data[columns].lt(0).any().any() or data[columns].mod(1).ne(0).any().any():
        raise ValueError("Kicking counts must be nonnegative integers")
    if "fg_blocked_list" not in data:
        raise ValueError("Missing blocked kick distances")
    blocked = []
    for row in data.to_dict("records"):
        value = row["fg_blocked_list"]
        distances = (
            []
            if pd.isna(value) or str(value).strip() == ""
            else [float(v) for v in str(value).split(";")]
        )
        if len(distances) != row["fg_blocked"] or any(
            not math.isfinite(v) or not 0 <= v <= 100 or v % 1 for v in distances
        ):
            raise ValueError("Blocked kick distance/count mismatch")
        blocked.append(distances)
    score = (
        data.fg_made * weights.get("fgm", 0)
        + (data.fg_missed + data.fg_blocked) * weights.get("fgmiss", 0)
        + data.pat_made * weights.get("xpm", 0)
        + (data.pat_missed + data.pat_blocked) * weights.get("xpmiss", 0)
    )
    for band, (low, high) in BANDS.items():
        suffix = band.replace("60p", "60_")
        blocks = pd.Series(
            [sum(low <= v <= high for v in ds) for ds in blocked], index=data.index
        )
        score += data["fg_made_" + suffix] * weights.get("fgm_" + band, 0)
        score += (data["fg_missed_" + suffix] + blocks) * weights.get(
            "fgmiss_" + band, 0
        )
    return score


class KickerBaseline:
    """Last eight observed games, shrunk toward the recent league mean (four games).

    No matchup/weather adjustment, DNP model, or calibrated interval is claimed.
    """

    def fit(self, raw, settings, season, week):
        data = numeric(raw, ["season", "week"])
        data = data.loc[(data.season * 100 + data.week) < season * 100 + week].copy()
        if data.empty or data.duplicated(["player_id", "season", "week"]).any():
            raise ValueError("Missing or duplicate kicker history")
        data["points"] = kicking_scores(data, settings)
        data["period"] = data.season * 100 + data.week
        data = data.sort_values("period")
        # Do not use a player's old-team role as current-team evidence.
        self.history = data
        self.cutoff = int(data.period.max())
        recent = data.loc[data.period.isin(sorted(data.period.unique())[-8:])]
        self.prior = float(recent.points.mean())
        return self

    def predict(self, player_id, team):
        own = self.history.loc[
            (self.history.player_id == player_id) & (self.history.team == team)
        ].tail(8)
        if len(own) < 4:
            return None, len(own)
        return float((own.points.sum() + 4 * self.prior) / (len(own) + 4)), len(own)


def specialist_context(
    roster, details, schedule, raw, settings, *, season, week, as_of, kicker_slots=1
):
    from fantasyfootball.lineups.weekly import WeeklyLineupPlanner

    rows = []
    specialist_details = {}
    for row in roster.to_dict("records"):
        sid = str(row["sleeper_id"])
        detail = details.get(sid, {})
        pos = detail.get("position") or row.get("pos")
        if pos not in {"K", "DEF"}:
            continue
        row["specialist_position"] = pos
        row["canonical_id"] = row.get("player_id")
        row["player_id"] = "sleeper:" + sid
        row["player_name"] = detail.get("full_name") or (
            sid + " defense" if pos == "DEF" else row.get("player_name")
        )
        # Reuse the common schedule/status logic without treating these as offensive forecasts.
        row["pos"] = pos
        specialist_details[sid] = dict(detail)
        if pos == "DEF":
            specialist_details[sid].update(
                team=detail.get("team") or sid, status="Active"
            )
        rows.append(row)
    if not rows:
        return pd.DataFrame(), {"status": "no_specialists"}
    context = WeeklyLineupPlanner().availability(
        pd.DataFrame(rows),
        specialist_details,
        schedule,
        season=season,
        week=week,
        as_of=as_of,
        supported_positions=("K", "DEF"),
    )
    context["pos"] = context.specialist_position
    context["projected_points"] = float("nan")
    context["history_games"] = 0
    context["recommendation"] = "NOT MODELED"
    context["model_note"] = (
        "Defense points unavailable; current slot is not a recommendation."
    )
    metadata = {
        "method": "Kicking-only eight-game mean with four-game league shrinkage",
        "limitations": "Research baseline; no weather/opponent adjustment, injury probability, or calibrated range. Defense forecasts unavailable.",
    }
    model = None
    if raw is not None and not raw.empty:
        try:
            model = KickerBaseline().fit(raw, settings, season, week)
            metadata["history_cutoff"] = model.cutoff
        except ValueError as exc:
            metadata["kicker_blocker"] = str(exc)
    else:
        metadata["kicker_blocker"] = "No kicking snapshot; refresh data."
    for index, row in context.iterrows():
        if row.pos != "K":
            continue
        context.loc[index, "model_note"] = (
            "Insufficient current-team history or unsupported scoring."
        )
        if model is not None and row.availability in {"eligible", "locked_starter"}:
            points, count = model.predict(row.canonical_id, row.get("team"))
            context.loc[index, "history_games"] = count
            if points is not None:
                context.loc[index, "projected_points"] = points
                context.loc[index, "model_note"] = (
                    "Kicking-only baseline; no calibrated range."
                )
    kickers = context.loc[context.pos == "K"]
    locked = kickers.loc[kickers.availability == "locked_starter"]
    eligible = kickers.loc[kickers.availability == "eligible"]
    # This report supports one K slot only; never silently fill a multi-kicker league.
    starter_slots = kicker_slots
    if starter_slots == 1 and len(locked) == 1:
        context.loc[locked.index, "recommendation"] = "LOCKED STARTER"
    elif (
        starter_slots == 1
        and not eligible.empty
        and eligible.projected_points.notna().all()
        and not kickers.availability.eq("unknown").any()
    ):
        chosen = eligible.projected_points.idxmax()
        context.loc[eligible.index, "recommendation"] = "BENCH (BASELINE)"
        context.loc[chosen, "recommendation"] = "START (BASELINE)"
    return context, metadata
