"""Assess complete trade packages by marginal roster value, without positional rules."""


class RosterNeedsPolicy:
    def assess(self, calculator, mine, after, result):
        reasons = []
        if result["status"] != "estimated":
            return {"eligible": False, "reasons": ["Incomplete forecast coverage"]}
        if round(result["my_gain"], 1) <= 0 or round(result["partner_gain"], 1) <= 0:
            reasons.append("Does not improve both teams projected roster value")
        diagnostics = {}
        if calculator.value_model is not None:
            outgoing = set(result["give"] + result["my_drops"])
            without = calculator.value_model.total(mine - outgoing)
            before = sum(row["my_before"]["points"] for row in result["weekly"])
            after_value = sum(row["my_after"]["points"] for row in result["weekly"])
            diagnostics = {
                "outgoing_opportunity_cost": before - without,
                "incoming_marginal_value": after_value - without,
                "method": "expected remaining-season lineup points with replacement alternatives",
            }
        return {"eligible": not reasons, "reasons": reasons, **diagnostics}
