"""Email-safe trade scenarios with explicit units and weekly comparisons."""

from html import escape


def render_trades(report, team_name):
    subject = (
        f"{team_name} - Week {report['week']} Trade Opportunities ({report['season']})"
    )
    lines = [subject, "As of " + report["as_of"]]
    sections = [
        "<h1>" + escape(subject) + "</h1>",
        "<p>As of " + escape(report["as_of"]) + "</p>",
    ]

    def paragraph(text):
        lines.append(text)
        sections.append("<p>" + escape(text) + "</p>")

    if report.get("deadline"):
        paragraph(report["deadline"]["description"])
        paragraph(
            f"Review period: {report['deadline']['review_days']} days. Trades accepted before the deadline can finish processing afterward."
        )
    if report["status"] == "closed":
        paragraph(report["reason"])
    else:
        weeks = report["weeks"]
        paragraph(
            f"Weeks {weeks[0]}-{weeks[-1]}: expected remaining-season lineup-point change, including FLEX, byes, availability scenarios, and waiver alternatives."
        )
        if report.get("roster_strengths"):
            sections.append("<h2>Your roster relative to the league</h2>")
            paragraph(
                "Position strength is the expected remaining-season lineup value lost if those players were replaced from the waiver pool. FLEX and depth are included; position values overlap and should not be summed."
            )
            rows = []
            for strength in report["roster_strengths"]:
                line = f"{strength['position']}: {strength['ros_value_above_replacement']:.1f} points above replacements; rank {strength['rank']}/{strength['teams_evaluated']}"
                lines.append(line)
                rows.append(
                    f"<tr><td>{escape(strength['position'])}</td><td>{strength['ros_value_above_replacement']:.1f}</td><td>{strength['league_median']:.1f}</td><td>{strength['rank']}/{strength['teams_evaluated']}</td></tr>"
                )
            sections.append(
                '<table cellpadding="8" border="1"><caption>ROS replacement premium; higher is stronger</caption><tr><th scope="col">Position</th><th scope="col">Your points</th><th scope="col">League median</th><th scope="col">Rank</th></tr>'
                + "".join(rows)
                + "</table>"
            )
        if report.get("asset_targets"):
            sections.append("<h2>Highest-value acquisition targets</h2>")
            paragraph(
                "Gain if acquired with one roster slot freed. The acquisition price is not included; the displaced player is a roster-space comparison, not a fair trade offer."
            )
            for target in report["asset_targets"]:
                player = report["players"][target["player_id"]]
                displaced = report["players"][target["displaced_player_id"]]
                paragraph(
                    f"{player['name']} ({player['pos']}, {player['team']}): {target['marginal_ros_gain']:+.1f} expected ROS lineup points; compared with freeing {displaced['name']}'s slot."
                )
        sections.append("<h2>Trade packages</h2>")
        if report.get("unsupported_scoring"):
            paragraph(
                "Scoring not modeled: " + ", ".join(report["unsupported_scoring"])
            )
        unknown = report.get("unknown_player_weeks", 0)
        if unknown:
            paragraph(
                f"Coverage: {unknown} player-weeks lack a usable forecast. Trades involving an incomplete team comparison are omitted."
            )
        if report.get("excluded_reserve_players") or report.get(
            "unavailable_player_weeks"
        ):
            paragraph(
                "Reserve/taxi players are excluded; currently unavailable players remain unavailable throughout this scenario."
            )
        if not report["opportunities"]:
            paragraph(
                "No evaluated one-for-one package improves both teams' expected remaining-season roster value. No forced recommendation."
            )

        def label(pid):
            p = report["players"][pid]
            return f"{p['name']} ({p['pos']}, {p['team']})"

        for trade in report["opportunities"]:
            title = (
                f"With roster {trade['partner_roster']}: give "
                + ", ".join(map(label, trade["give"]))
                + "; get "
                + ", ".join(map(label, trade["receive"]))
            )
            lines.append(title)
            sections.append("<h2>" + escape(title) + "</h2>")
            paragraph(
                f"Your lineup: {trade['my_gain']:+.1f} points total. Their lineup: {trade['partner_gain']:+.1f} points total."
            )
            assessment = trade.get("recommendation", {})
            if "incoming_marginal_value" in assessment:
                paragraph(
                    f"Incoming benefit: {assessment['incoming_marginal_value']:+.1f} expected points. Outgoing opportunity cost: {assessment['outgoing_opportunity_cost']:.1f} points."
                )
            rows = []
            for week in trade["weekly"]:
                summary = f"Week {week['week']}: you {week['my_gain']:+.1f}; them {week['partner_gain']:+.1f}"
                lines.append(summary)
                rows.append(
                    f"<tr><td>{week['week']}</td><td>{week['my_gain']:+.1f}</td><td>{week['partner_gain']:+.1f}</td></tr>"
                )
            sections.append(
                '<table cellpadding="8" cellspacing="0" border="1"><caption>Projected weekly lineup-point change</caption><thead><tr><th scope="col">Week</th><th scope="col">You</th><th scope="col">Partner</th></tr></thead><tbody>'
                + "".join(rows)
                + "</tbody></table>"
            )
            lowest = min(w["my_after"]["filled"] for w in trade["weekly"])
            slot_count = trade["weekly"][0]["my_after"]["slots"]
            if lowest < slot_count - 0.05:
                paragraph(
                    f"Availability scenarios can leave starters uncovered: lowest weekly average {lowest:.1f} of {slot_count} slots filled after this trade."
                )
        paragraph(
            "Expected values use current-role forecasts and historical scoring-appearance rates as an availability proxy, not a calibrated injury model. Future roles and injury recoveries are held unchanged; multi-week gains do not have calibrated confidence intervals."
        )
        paragraph(
            "Ranked by your expected ROS gain; one proposal per partner. Weekly streaming assumes access to current waiver alternatives; claim competition, FAAB, drop/reacquisition costs, and trade-review delays are not modeled. Future pick value stays separate. No trade offers are sent."
        )
    inventory = report.get("pick_inventory")
    if inventory:
        sections.append("<h2>Next-year draft capital</h2>")
        lines.append("Next-year draft capital")
        if inventory["status"] == "unavailable":
            paragraph(inventory["reason"])
        else:
            mine = [
                p for p in inventory["picks"] if p["owner_id"] == report["my_roster"]
            ]
            paragraph(
                f"{inventory['season']} picks owned: "
                + ", ".join(
                    f"R{p['round']} (original roster {p['original_roster']})"
                    for p in mine
                )
                if mine
                else "No next-year picks owned in this inventory."
            )
            if inventory["status"] == "rounds_confirmed":
                paragraph(
                    f"{inventory['rounds']} rounds confirmed. Next-year draft order and keeper costs remain unspecified."
                )
            if inventory["status"] == "provisional":
                paragraph(
                    f"Provisional: assumes the {inventory['source_season']} draft's {inventory['rounds']} rounds; next-year draft and keeper costs are not configured. League draft_rounds setting: {inventory.get('round_setting')}."
                )
            valued = [p for p in mine if p.get("value_scenario") and p["round"] <= 3]
            if valued:
                paragraph(
                    "Draft-capital scenarios, refreshed from current standings. Index uses 100 / sqrt(overall pick); it is a rank heuristic, not a fair trade price or fantasy points."
                )
                if inventory.get("draft_order_rule") == "unknown":
                    paragraph(
                        "Draft order rule is unconfirmed: the main index weights all slots equally. The standings column is conditional on reverse standings."
                    )
                rows = []
                for pick in valued:
                    value = pick["value_scenario"]
                    conditional = value.get("reverse_standings_if_season_ended_today")
                    scenario = (
                        f"{conditional['capital_index']:.1f}"
                        if conditional
                        else "Unavailable"
                    )
                    label = (
                        f"R{pick['round']} / original roster {pick['original_roster']}"
                    )
                    lines.append(
                        f"{label}: index {value['capital_index']:.1f}; reverse-standings scenario {scenario}"
                    )
                    rows.append(
                        f"<tr><td>{escape(label)}</td><td>{value['capital_index']:.1f}</td><td>{scenario}</td></tr>"
                    )
                sections.append(
                    '<table cellpadding="8" border="1"><caption>First three rounds: draft-capital index</caption><tr><th scope="col">Pick</th><th scope="col">Index</th><th scope="col">Reverse standings today</th></tr>'
                    + "".join(rows)
                    + "</table>"
                )
            paragraph(
                "Pick IDs and full-round overall ranges are saved with the calculator. Include picks in a custom proposal to see the current lineup effect; future pick value remains unpriced. No fair-price pick recommendation is made yet."
            )
    html = (
        '<!doctype html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;color:#182230;max-width:760px;margin:auto;padding:16px">'
        + "".join(sections)
        + "</body></html>"
    )
    return subject, "\n\n".join(lines), html
