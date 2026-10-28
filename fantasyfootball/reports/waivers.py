"""Email-safe waiver tables with explicit scope and budget limitations."""

import json
from html import escape

import pandas as pd


def render_waivers(plan_dir):
    path = plan_dir / "waivers.csv"
    if not path.exists():
        return (
            "<h2>Waiver wire</h2><p>Waiver rankings unavailable for this snapshot.</p>",
            "\nWaiver rankings unavailable.",
        )
    meta = json.loads((plan_dir / "waiver-report.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(path)
    balance = meta.get("remaining_faab")
    intro = (
        f"FAAB remaining: ${balance}"
        if balance is not None
        else "FAAB balance unavailable; dollar recommendations withheld."
    )
    note = "Weekly lineup gain uses your league's supported offensive scoring."
    html = [
        "<h2>Waiver wire by position</h2><p>"
        + escape(intro)
        + "</p><p>"
        + escape(note)
        + "</p>"
    ]
    plain = ["\nWaiver wire", intro, note]

    def number(x):
        return f"{x:.1f}" if pd.notna(x) else "Unavailable"

    for category in meta["categories"]:
        data = frame.loc[frame.category.eq(category)]
        html.append(
            "<h3>"
            + escape(category)
            + (" (unranked watchlist)" if category == "DEF" else "")
            + "</h3>"
        )
        if data.empty:
            html.append("<p>No eligible modeled candidates.</p>")
            continue
        if category == "DEF":
            explanation = "Defense points and FAAB not modeled; available teams are listed alphabetically."
            html.append("<p>" + explanation + "</p>")
            plain.append("DEF: " + explanation)
            html.append(
                '<table border="1" cellpadding="6" cellspacing="0"><tr><th>Defense</th><th>Opponent</th><th>Watch</th></tr>'
            )
            for row in data.sort_values("player_name").to_dict("records"):
                warning = (
                    str(row.get("warning")) if pd.notna(row.get("warning")) else ""
                )
                warning = warning.replace(
                    "Defense points and FAAB not modeled.", ""
                ).strip()
                values = [str(row["player_name"]), str(row["opp"]), warning]
                html.append(
                    "<tr>"
                    + "".join("<td>" + escape(v) + "</td>" for v in values)
                    + "</tr>"
                )
                plain.append("DEF | " + " | ".join(values))
            html.append("</table>")
            continue
        if category == "K":
            explanation = "Kicker points use a kicking-only baseline; prediction ranges unavailable."
            html.append("<p>" + explanation + "</p>")
            plain.append(explanation)
        html.append(
            '<table border="1" cellpadding="6" cellspacing="0"><tr><th>Rank / player</th><th>Pos / opponent</th><th>Points</th><th>Lineup gain</th><th>FAAB range</th><th>Watch</th></tr>'
        )
        for row in data.to_dict("records"):
            bid = (
                f"${int(row['faab_low'])}-${int(row['faab_high'])}"
                if pd.notna(row["faab_low"]) and pd.notna(row["faab_high"])
                else "Unavailable"
            )
            rank = str(int(row["rank"])) if pd.notna(row["rank"]) else "Unranked"
            watch = str(row.get("warning")) if pd.notna(row.get("warning")) else ""
            watch = watch.replace("; recheck before kickoff", "")
            values = [
                rank + " / " + str(row["player_name"]),
                str(row["pos"]) + " / " + str(row["opp"]),
                number(row["projected_points"]),
                number(row["lineup_gain"]),
                bid,
                watch,
            ]
            html.append(
                "<tr>" + "".join("<td>" + escape(v) + "</td>" for v in values) + "</tr>"
            )
            plain.append(category + " | " + " | ".join(values))
        html.append("</table>")
    comparison_path = plan_dir / "waiver-add-drop.csv"
    if comparison_path.exists():
        comparisons = pd.read_csv(comparison_path)
        comparisons = comparisons.loc[
            comparisons.add_pos.isin(["RB", "WR", "TE"])
            & comparisons.drop_pos.isin(["RB", "WR", "TE"])
        ].head(10)
        guidance = (
            "RB/WR/TE and FLEX scenarios; net change includes the dropped player."
        )
        html.append(
            "<h2>Add/drop what-if comparisons</h2><p>" + escape(guidance) + "</p>"
        )
        plain.extend(["\nAdd/drop what-if comparisons", guidance])
        if comparisons.empty:
            reason = meta.get(
                "add_drop_reason", "No eligible, feasible offensive bench-drop pairs."
            )
            html.append("<p>" + escape(reason) + "</p>")
            plain.append(reason)
        else:
            html.append(
                '<table border="1" cellpadding="6" cellspacing="0"><tr><th>Add</th><th>Drop scenario</th><th>Net weekly lineup change</th><th>Next 3 weeks: slots covered before -&gt; after</th></tr>'
            )
            for row in comparisons.to_dict("records"):
                values = [
                    str(row["add_player_name"]) + " (" + str(row["add_pos"]) + ")",
                    str(row["drop_player_name"]) + " (" + str(row["drop_pos"]) + ")",
                    f"{row['net_gain']:+.1f}",
                    str(row.get("future_coverage", "Not recorded")),
                ]
                html.append(
                    "<tr>"
                    + "".join("<td>" + escape(v) + "</td>" for v in values)
                    + "</tr>"
                )
                plain.append(" | ".join(values))
            html.append("</table>")
    return "".join(html), "\n".join(plain)
