from __future__ import annotations

from typing import Any, Dict, List

# Template actions keyed by method type
_ACTION_TEMPLATES = {
    "dowhy": "Reduce variance in '{feature}' — causal effect size {effect_size:.3f} on outcome.",
    "granger": "Investigate lag dependency of '{feature}' — Granger causality confidence {confidence:.3f}.",
    "correlation": "Monitor and stabilize '{feature}' — correlation-based proxy for causal effect.",
    "correlation_fallback": "Inspect '{feature}' for data quality issues — used as fallback estimator.",
    "default": "Review '{feature}' and apply corrective controls.",
}


def generate_actions(
    optimized_causes: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Map each optimized root cause to a concrete, ranked action.
    """
    actions = []
    for priority, cause in enumerate(optimized_causes, start=1):
        template = _ACTION_TEMPLATES.get(cause.get("method", ""), _ACTION_TEMPLATES["default"])
        description = template.format(**cause)
        actions.append({
            "description": description,
            "target_feature": cause["feature"],
            "adjustment": {
                "direction": "decrease" if cause["effect_size"] > 0 else "increase",
                "magnitude": round(cause["effect_size"], 4),
            },
            "expected_impact": round(cause.get("optimization_weight", cause["effect_size"]), 4),
            "priority": priority,
        })
    return actions
