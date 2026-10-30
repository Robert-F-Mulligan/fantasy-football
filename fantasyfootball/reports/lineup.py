"""Action-first lineup presentation shared by HTML and plain-text emails."""

import re
from html import escape
from math import isfinite

import pandas as pd


def _text(value):
    return str(value) if pd.notna(value) else ""


def _finite(value):
    try:
        return isfinite(float(value))
    except (TypeError, ValueError):
        return False


def kickoff_label(value):
    """Convert schedule timestamps to Eastern, preserving the seasonal DST label."""
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return "Kickoff unavailable"
    return timestamp.tz_convert("America/New_York").strftime("%a %b %d, %I:%M %p %Z")


def _notes(row):
    status = _text(row.get("availability"))
    labels = {
        "locked_starter": "Locked starter; preweek estimate",
        "locked_bench": "Locked bench",
        "no_scheduled_game": "Bye or schedule unavailable",
        "reserve": "Reserve / taxi",
        "unavailable": "Unavailable",
        "unknown": "Availability unknown",
        "unsupported_position": "Not modeled",
    }
    notes = [labels[status]] if status in labels else []
    warning = _text(row.get("warning"))
    if warning and warning != "Bye or incomplete schedule; excluded":
        warning = warning.removesuffix("; recheck before kickoff")
        notes.append(warning)
    games = row.get("history_games")
    if _finite(games) and float(games) < 4:
        notes.append(f"Limited history: {int(games)} games")
    if status in {"eligible", "locked_starter", "locked_bench"} and not _finite(
        row.get("projected_points")
    ):
        notes.append("Forecast unavailable")
    return "; ".join(notes)


def render_lineup_brief(board, lineup, *, slots=None, as_of=None):
    """Compare membership, not slot pairs: moving a starter into FLEX is not a swap."""
    selected = set(lineup.player_id)
    current = board.loc[
        board.starter_slot.fillna("").ne("") & board.pos.isin(["QB", "RB", "WR", "TE"])
    ]
    current_ids = set(current.player_id)
    added = board.loc[board.player_id.isin(selected - current_ids)]
    removed = current.loc[~current.player_id.isin(selected)]
    actions = []
    if not added.empty:
        actions.append("Start: " + ", ".join(added.player_name.map(_text)))
    if not removed.empty:
        actions.append("Bench: " + ", ".join(removed.player_name.map(_text)))
    if not actions:
        actions.append("Keep your current offensive starters.")
    assigned = lineup.set_index("player_id").slot.to_dict()
    moves = [
        f"{_text(row.player_name)}: {row.starter_slot} to {assigned[row.player_id]}"
        for row in current.itertuples()
        if row.player_id in selected
        and re.sub(r"\d+$", "", row.starter_slot)
        != re.sub(r"\d+$", "", assigned[row.player_id])
    ]
    if moves:
        actions.append("Slot assignments: " + "; ".join(moves))

    # Incomplete, unavailable, or unprojected incumbents are not a zero-point baseline.
    comparable = (
        len(current) == len(lineup)
        and set(current.starter_slot) == set(lineup.slot)
        and current.starter_slot.is_unique
        and current.availability.isin(["eligible", "locked_starter"]).all()
        and current.projected_points.map(_finite).all()
        and lineup.projected_points.map(_finite).all()
    )
    if comparable and (not added.empty or not removed.empty):
        gain = lineup.projected_points.sum() - current.projected_points.sum()
        actions.append(
            f"Lineup change: {gain:+.1f} projected points versus your current offense."
        )
    elif not comparable:
        actions.append(
            "Point gain unavailable: the current offense is incomplete or has unavailable forecasts/players."
        )
    if comparable and len(added) == len(removed) == 1:
        new, old = added.iloc[0], removed.iloc[0]
        bounds = [
            new.get("prediction_lower"),
            new.get("prediction_upper"),
            old.get("prediction_lower"),
            old.get("prediction_upper"),
        ]
        if all(_finite(v) for v in bounds) and max(bounds[0], bounds[2]) <= min(
            bounds[1], bounds[3]
        ):
            actions.append(
                f"Close call: {_text(new.player_name)} / {_text(old.player_name)}. Historical ranges overlap; the projected edge is uncertain."
            )

    html = (
        "<h2>Your lineup actions</h2><ul>"
        + "".join(
            '<li style="margin-bottom:8px">' + escape(action) + "</li>"
            for action in actions
        )
        + "</ul>"
    )
    plain = "Your lineup actions\n" + "\n".join(actions)
    contingency_html, contingency_text = render_contingencies(
        board, lineup, slots, as_of
    )
    html += contingency_html
    plain += contingency_text
    starts = lineup[["player_id", "slot"]].merge(
        board, on="player_id", validate="one_to_one"
    )
    bench = board.loc[~board.player_id.isin(selected)].sort_values(
        ["pos", "projected_points", "player_name"],
        ascending=[True, False, True],
        na_position="last",
    )
    for title, frame in [("Recommended starters", starts), ("Bench", bench)]:
        html += f'<h2>{title}</h2><table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse"><tr><th align="left" scope="col">Slot / player</th><th align="left" scope="col">Matchup / kickoff</th><th align="right" scope="col">Points</th></tr>'
        plain += "\n\n" + title
        for row in frame.to_dict("records"):
            slot = _text(row.get("slot")) or _text(row.get("pos"))
            name = _text(row.get("player_name")) or _text(row.get("sleeper_id"))
            opponent = _text(row.get("opp")) or "Unavailable"
            kickoff = kickoff_label(row.get("kickoff"))
            points = (
                f"{row['projected_points']:.1f}"
                if _finite(row.get("projected_points"))
                else "Unavailable"
            )
            notes = _notes(row)
            html += f'<tr><td style="border-top:1px solid #d6dee5"><b>{escape(slot)} · {escape(name)}</b>'
            if notes:
                html += f"<br><small>{escape(notes)}</small>"
            html += f'</td><td style="border-top:1px solid #d6dee5">{escape(opponent)}<br><small>{escape(kickoff)}</small></td><td align="right" style="border-top:1px solid #d6dee5">{escape(points)}</td></tr>'
            plain += f"\n{slot} | {name} | {opponent} | {kickoff} | {points} points" + (
                f" | {notes}" if notes else ""
            )
        html += "</table>"
    return html, plain


def render_contingencies(board, lineup, slots, as_of):
    from fantasyfootball.lineups.contingencies import (
        combined_injury_contingency,
        injury_contingencies,
    )

    scenarios = injury_contingencies(board, lineup, slots, as_of)
    if not scenarios:
        return "", ""
    lines = []
    for scenario in scenarios:
        prefix = f"If {scenario['starter']} is ruled out: "
        option = scenario["option"]
        if option is None:
            lines.append(
                prefix
                + "no unflagged, projected bench replacement with confirmed timing can fill the lineup."
            )
            continue
        assignments = "; ".join(
            f"{row['player_name']} to {row['slot']}"
            + (f" (from {row['from_slot']})" if row["from_slot"] else "")
            for row in option["assignments"]
        )
        timing = (
            "Available at the starter's kickoff"
            if option["later"]
            else "Earlier decision required; do not wait for the starter's kickoff"
        )
        lines.append(
            prefix
            + assignments
            + f". Backup projection: {option['projected_points']:.1f} points. {timing}. Act before {kickoff_label(option['deadline'])}."
        )
    joint = combined_injury_contingency(board, lineup, slots, as_of)
    if joint is not None:
        prefix = "If all are ruled out (" + ", ".join(joint["starters"]) + "): "
        if joint["status"] == "unavailable":
            lines.append(
                prefix
                + "the unflagged, projected bench players with confirmed timing cannot fill every opening. The individual backup plans cannot all be used together."
            )
        else:
            assignments = "; ".join(
                f"{row['player_name']} to {row['slot']}"
                + (f" (from {row['from_slot']})" if row["from_slot"] else "")
                for row in joint["assignments"]
            )
            timing = "Earlier decision required. " if joint["earlier"] else ""
            lines.append(
                prefix
                + assignments
                + ". "
                + timing
                + f"Make this combined decision before {kickoff_label(joint['deadline'])}. Each backup is used once."
            )
    note = "Individual plans assume only that starter is out. The combined plan, when shown, assumes all listed starters are out; their status may not be confirmed before its deadline."
    if joint is None:
        note = "Each option assumes only that starter is out and the other starters remain available."
    html = (
        "<h2>Injury backup plan</h2><ul>"
        + "".join("<li>" + escape(line) + "</li>" for line in lines)
        + "</ul><p>"
        + note
        + "</p>"
    )
    return html, "\n\nInjury backup plan\n" + "\n".join(lines) + "\n" + note
