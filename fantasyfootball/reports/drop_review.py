"""Shared plain-text/HTML-safe forecast evidence for trade reports."""


def review_lines(report):
    assessment = report.get("drop_assessment")
    if not assessment:
        return []
    lines = [f"Forecast history cutoff: {report.get('forecast_cutoff', 'unknown')}. Drop review: {assessment['status'].replace('_', ' ')}."]
    if assessment["status"] == "incomplete":
        return lines + [assessment["reason"]]
    if assessment.get("keeper_review_required"):
        lines.append("Keeper value is not included in this drop ranking; resolve keeper rights before releasing a player.")
    lines.append("Near ties: within one total ROS lineup point in every tested scenario. This is a display tolerance, not statistical significance. Scenario ranges are not confidence intervals.")
    evidence = report.get("player_evidence", {})
    for row in assessment["candidates"]:
        if not row["near_best_in_all_scenarios"] and not row["flags"]:
            continue
        e = evidence.get(row["player_id"], {})
        text = f"{row['name']}: dropping costs {row['loss_low']:.1f} to {row['loss_high']:.1f} modeled ROS lineup points."
        if row["near_best_in_all_scenarios"]:
            text += " Among lowest-cost options across scenarios."
        if row["flags"]:
            text += " Review: " + ", ".join(f.replace("_", " ") for f in row["flags"]) + "."
            text += f" Last observed: {e.get('last_observed_period')}; injury designation: {e.get('injury_status') or 'none reported'}."
        if row["bye_weeks"]:
            text += " Bye: " + ", ".join(map(str, row["bye_weeks"])) + "."
        lines.append(text)
    return lines


def acquisition_lines(review):
    """Compact target-specific explanation, rendered once per acquisition."""
    if not review:
        return []
    if review["status"] in {"unavailable", "incomplete"}:
        return ["Roster-space review unavailable: " + review["reason"]]
    choices = [r for r in review["candidates"] if r["near_best_in_all_scenarios"]]
    if not choices:
        return ["No consistently lowest-cost drop across availability/workload scenarios; review the alternatives before making room."]
    names = "; ".join(
        f"{r['name']} ({r['loss_low']:.1f}-{r['loss_high']:.1f} lineup points lost)"
        for r in choices
    )
    lines = ["After this acquisition, lowest-cost roster-space options: " + names + "."]
    if len(choices) > 1:
        lines.append("These options are within one total ROS lineup point of the best in every scenario; there is no unique drop choice.")
    flagged = [r["name"] for r in choices if r["flags"]]
    if flagged:
        lines.append("Workload/injury evidence needs review for " + ", ".join(flagged) + ".")
    if review.get("keeper_review_required"):
        lines.append("Preserve keeper rights until their cost and eligibility are checked.")
    return lines
