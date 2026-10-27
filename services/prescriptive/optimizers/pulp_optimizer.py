from __future__ import annotations

from typing import Any, Dict, List

import pulp


def optimize(
    root_causes: List[Dict[str, Any]],
    budget: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Binary LP (0/1 knapsack): maximise total causal effect subject to a
    normalised IT-resource budget.

    Each root cause must carry a 'cost' field (0–1, normalised so all
    costs sum to 1.0).  The constraint is:

        sum(cost_i * x_i) <= B                   (budget fraction B in (0,1])

    Objective:

        max  sum(effect_size_i * confidence_i * x_i)
    """
    if not root_causes:
        return []

    n = len(root_causes)
    prob = pulp.LpProblem("rca_prescription", pulp.LpMaximize)

    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    # Objective: maximise impact weighted by confidence
    impacts = [rc["effect_size"] * rc["confidence"] for rc in root_causes]
    prob += pulp.lpSum(impacts[i] * x[i] for i in range(n))

    # Budget constraint: use explicit per-action cost (normalised)
    costs = [rc.get("cost", 1.0 / n) for rc in root_causes]
    prob += pulp.lpSum(costs[i] * x[i] for i in range(n)) <= budget

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    selected = []
    for i, var in enumerate(x):
        if pulp.value(var) == 1:
            selected.append({
                **root_causes[i],
                "optimization_weight": impacts[i],
            })
    return selected
