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
        market = report.get("market_reference")
        if market:
            paragraph(
                "Market reference: "
                + market.get("source", "Unavailable")
                + "; fetched "
                + market.get("fetched_at", "unknown")
            )
            sections.append(
                '<p><a href="https://fantasycalc.com/frequently-asked-questions">FantasyCalc market methodology</a></p>'
            )
            if market.get("league_type") in {1, 2}:
                paragraph(
                    "Fairness is provisional: these redraft market prices exclude your keeper rights and next-year picks. Custom scoring is only partially matched."
                )
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
            fairness = trade.get("fairness", {})
            comparison = fairness.get("player_market_comparison")
            if comparison:
                paragraph(
                    f"Player market reference: give {comparison['give_total']:,.0f}; receive {comparison['receive_total']:,.0f}. {comparison['direction'].capitalize()}. These are market units, not fantasy points; keeper and draft-pick value are assessed separately."
                )
            elif fairness:
                paragraph(
                    "Market comparison unavailable: "
                    + fairness.get("reason", "Comparable prices unavailable")
                )
            estimate = trade.get("offer_estimate", {})
            if estimate.get("status") == "conditional_estimate":
                verdicts = {
                    "both_benefit_in_modeled_scenarios": "Both teams benefit in modeled scenarios",
                    "favors_you_in_modeled_scenarios": "Favors you in modeled scenarios",
                    "favors_partner_in_modeled_scenarios": "Favors your partner in modeled scenarios",
                    "both_lose_in_modeled_scenarios": "Both teams lose in modeled scenarios",
                    "depends_on_assumptions": "Fairness depends on keeper and draft assumptions",
                }
                paragraph("Offer estimate: " + verdicts[estimate["verdict"]])
                me, them = estimate["my_total_change"], estimate["partner_total_change"]
                paragraph(
                    f"Two-season value change: you {me['low']:+.1f} to {me['high']:+.1f}; "
                    f"partner {them['low']:+.1f} to {them['high']:+.1f} point-equivalents. "
                    "Includes current lineup points, next-year draft capital, and keeper surplus. "
                    "Sensitivity range, not a confidence interval or acceptance probability."
                )
            elif estimate:
                paragraph("Offer estimate unavailable: " + estimate["reason"])
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
    if report.get("fairness_assumptions"):
        sections.append("<h2>How offer value is estimated</h2>")
        paragraph(
            "Next season carries forward current performance and participation, with historical performance used for currently unavailable players. "
            "Keeper scenarios test eligibility, round costs, the two-keeper limit, and the picks needed to pay those costs. "
            "Draft selections follow current standings, with keeper-related rank shifts; next-season surplus points receive weights of 0.75 and 1.0. "
            "These sensitivity choices are not fitted probabilities and do not forecast rookies or offseason changes."
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
                    f"{inventory['rounds']} rounds confirmed. Final draft order and keeper costs remain unspecified."
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
                        "Draft order rule is unconfirmed: the main index weights all slots equally. Selections remain full-round ranges until an order rule is supplied."
                    )
                if inventory.get("draft_order_rule") == "reverse_standings":
                    paragraph(
                        "Projected snake order if the season ended today: lowest winning percentage picks first, then lower points scored. Even rounds reverse. Exact ties remain ranges; playoffs and future results can change the order."
                    )
                rows = []
                for pick in valued:
                    value = pick["value_scenario"]
                    selection = value.get("selection", "Unassigned")
                    positions = value.get("projected_overall_picks", [])
                    overall = (
                        str(positions[0])
                        if len(positions) == 1
                        else (
                            f"{min(positions)}-{max(positions)}"
                            if positions
                            else "Unassigned"
                        )
                    )
                    label = (
                        f"R{pick['round']} / original roster {pick['original_roster']}"
                    )
                    lines.append(
                        f"{label}: projected {selection}, overall {overall}; index {value['capital_index']:.1f}"
                    )
                    rows.append(
                        f"<tr><td>{escape(label)}</td><td>{escape(selection)}</td><td>{overall}</td><td>{value['capital_index']:.1f}</td></tr>"
                    )
                sections.append(
                    '<table cellpadding="8" border="1"><caption>First three rounds: projected selections</caption><tr><th scope="col">Pick</th><th scope="col">Selection</th><th scope="col">Overall</th><th scope="col">Index</th></tr>'
                    + "".join(rows)
                    + "</table>"
                )
            paragraph(
                "Pick IDs and full-round overall ranges are saved with the calculator. Include picks in a custom proposal to see the current lineup effect; future pick effects are estimated conditionally when saved fairness evidence is available."
            )
    html = (
        '<!doctype html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;color:#182230;max-width:760px;margin:auto;padding:16px">'
        + "".join(sections)
        + "</body></html>"
    )
    return subject, "\n\n".join(lines), html
