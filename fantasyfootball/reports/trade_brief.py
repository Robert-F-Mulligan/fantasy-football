"""Concise trade email: current roster gains separate from experimental pick costs."""

from html import escape


def render_trade_brief(report, team_name):
    subject = f"{team_name} - Week {report['week']} Trade Review ({report['season']})"
    lines, html = [subject], ["<h1>" + escape(subject) + "</h1>"]

    def paragraph(text):
        lines.append(text)
        html.append("<p>" + escape(text) + "</p>")

    def table(headers, rows):
        html.append(
            '<table cellpadding="7" cellspacing="0" border="1"><thead><tr>'
            + "".join('<th scope="col">' + escape(h) + "</th>" for h in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>"
                + "".join("<td>" + escape(str(x)) + "</td>" for x in row)
                + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )
        lines.extend(" | ".join(map(str, row)) for row in rows)

    def points(value):
        return "~0" if abs(value) < 1 else f"{value:+.0f}"

    def proxy(value, cost=False):
        if not value:
            return "Unavailable"
        low, high = (
            (-value["high"], -value["low"]) if cost else (value["low"], value["high"])
        )
        return f"about {low:.0f} to {high:.0f}"

    paragraph("As of " + report["as_of"])
    if report.get("deadline"):
        paragraph(report["deadline"]["description"])
    if report["status"] == "closed":
        paragraph(report["reason"])
    else:
        strengths = report.get("roster_strengths", [])
        size = report.get("league_team_count") or (
            strengths[0].get("league_teams") if strengths else None
        )
        if size:
            coverage = strengths[0]["teams_evaluated"] if strengths else 0
            paragraph(
                f"{size}-team league; complete roster comparisons available for {coverage} teams."
            )
        audit = report.get("model_audit", {})
        paragraph(
            "Current lineup gains are model forecasts. Next-year pick and keeper costs are experimental surplus-value proxies; there is no validated fair-price ceiling yet."
        )
        if audit.get("unresolved_keeper_rules"):
            paragraph(
                "Keeper rules still to confirm: "
                + "; ".join(audit["unresolved_keeper_rules"])
                + "."
            )
        offers = report.get("pick_trade_scenarios", {}).get("offers", [])
        if offers:
            html.append("<h2>Pick offers to review</h2>")
            for target_id in dict.fromkeys(o["target_id"] for o in offers):
                player = report["players"][target_id]
                title = f"Acquire {player['name']} ({player['pos']}, {player['team']})"
                html.append("<h3>" + escape(title) + "</h3>")
                lines.append(title)
                choices = [o for o in offers if o["target_id"] == target_id]
                ready = [o for o in choices if o["status"] == "estimated"]
                if ready:
                    t = ready[0]["trade"]
                    paragraph(
                        f"Current-season lineup change: you {points(t['my_gain'])} points; seller {points(t['partner_gain'])} points. Pick compensation is separate below."
                    )
                rows = []
                for o in choices:
                    pick = o["pick"]
                    label = (
                        f"{pick['season']} "
                        + pick.get("value_scenario", {}).get(
                            "selection", f"Round {pick['round']}"
                        )
                        + f" (original team {pick['original_roster']})"
                    )
                    if o["status"] != "estimated":
                        rows.append([label, "—", o["reason"], "—"])
                        continue
                    t = o["trade"]
                    estimate = t.get("offer_estimate", {})
                    drop = ", ".join(
                        report["players"][pid]["name"] for pid in t["my_drops"]
                    )
                    rows.append(
                        [
                            label,
                            drop,
                            proxy(estimate.get("my_future_change"), True),
                            proxy(estimate.get("partner_future_change")),
                        ]
                    )
                table(
                    [
                        "You give",
                        "You drop",
                        "Your future-cost proxy",
                        "Seller future-credit proxy",
                    ],
                    rows,
                )
        swaps = report.get("opportunities", [])[:3]
        if swaps:
            html.append("<h2>Player swaps to examine</h2>")
            for trade in swaps:
                names = lambda ids: ", ".join(
                    report["players"][pid]["name"] for pid in ids
                )
                paragraph(
                    f"Give {names(trade['give'])}; receive {names(trade['receive'])}. Current-season gain: you {points(trade['my_gain'])}; partner {points(trade['partner_gain'])} points."
                )
                interval = trade.get("uncertainty", {}).get("you", {})
                if interval.get("status") == "estimated":
                    paragraph(
                        f"Fixed-starter plan: {points(interval['expected_gain'])} points; nominal 80% prediction interval {interval['prediction_lower']:+.0f} to {interval['prediction_upper']:+.0f}."
                    )
                comparison = trade.get("fairness", {}).get("player_market_comparison")
                if comparison:
                    paragraph("Market reference: " + comparison["direction"] + ".")
        if not offers and not swaps:
            paragraph("No supported trade comparisons are available for this snapshot.")
        paragraph(
            "Prospective check: frozen scoring forecasts are tracked against no-change and recent-four-game baselines. Historical interval checks use synthetic trades; live predictive advantage is not established. Keeper and pick ranges are scenarios, not confidence intervals."
        )
    body = (
        '<!doctype html><html><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;color:#182230;max-width:760px;margin:auto;padding:16px">'
        + "".join(html)
        + "</body></html>"
    )
    return subject, "\n\n".join(lines), body
