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
