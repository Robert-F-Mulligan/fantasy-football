"""Evidence boundaries for trade recommendations; unresolved rules stay explicit."""


def audit_trade_model(fairness, report):
    rules = fairness.get("rules", {})
    fields = {
        "cost_basis": "Original versus latest keeper round",
        "cost_follows_trade": "Whether round cost follows a traded player",
        "keep_count_follows_trade": "Whether consecutive keep count follows a traded player",
        "before_round_one_policy": "Treatment of costs earlier than Round 1",
    }
    unresolved = [label for key, label in fields.items() if rules.get(key) is None]
    return {
        "version": 1,
        "status": "research_only_for_future_price",
        "price_guidance_enabled": False,
        "confirmed_keeper_rules": {
            k: rules.get(k) for k in ["round_penalty", "max_consecutive_keeps"]
        },
        "unresolved_keeper_rules": unresolved,
        "findings": [
            {
                "code": "mixed_value_scales",
                "severity": "high",
                "finding": "Current lineup points and next-year standalone surplus are different utility measures; their sum is not a validated fair price",
                "action": "Show current gain and future-cost proxy separately in the main email",
            },
            {
                "code": "future_curve_unvalidated",
                "severity": "high",
                "finding": "The current-player draft curve does not forecast next year's rookies, roles, or draft demand",
                "action": "Keep pick pricing conditional; do not publish a fair-price ceiling",
            },
            {
                "code": "sensitivity_not_probability",
                "severity": "medium",
                "finding": "Keeper modes, rank shifts and future weights are chosen scenarios, not learned probabilities",
                "action": "Do not average scenario counts into acceptance or fairness odds",
            },
            {
                "code": "prospective_validation_pending",
                "severity": "high",
                "finding": "Synthetic historical coverage does not establish an edge on archived live offers",
                "action": "Seal fixed plans and baselines before kickoff; score only settled, resolved horizons",
            },
        ],
        "historical_interval_check": report.get("uncertainty_validation", {}).get(
            "status", "unavailable"
        ),
    }
