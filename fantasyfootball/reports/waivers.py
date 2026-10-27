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
    audit_path = plan_dir / "plan-report.json"
    audit = (
        json.loads(audit_path.read_text(encoding="utf-8"))
        if audit_path.exists()
        else {}
    )
    omitted = ", ".join(audit.get("unsupported_scoring", {})) or "none recorded"
    note = (
        meta["limits"]
        + " "
        + meta["lineup_gain_note"]
        + " Supported offensive scoring only; omitted rules: "
        + omitted
        + ". Kicker estimates use a separate kicking-only baseline."
    )
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
            if row["pos"] == "K":
                watch += " Kicking-only baseline; no calibrated range."
            if row["pos"] == "DEF":
                watch += " Defense points and FAAB not modeled."
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
    return "".join(html), "\n".join(plain)
