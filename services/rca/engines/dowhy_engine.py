from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

try:
    import dowhy
    from dowhy import CausalModel
    DOWHY_AVAILABLE = True
except ImportError:
    DOWHY_AVAILABLE = False


def estimate_effects(
    rows: List[Dict[str, Any]],
    causal_graph: Dict[str, List[str]],
    outcome_col: Optional[str] = None,
    anomaly_indices: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Estimate causal effect of each upstream variable on the outcome.

    When anomaly_indices is supplied the returned effect_size is the
    anomaly-contribution score: |causal_effect| × |mean_delta_in_fault_window|.
    This correctly ranks variables that both (a) causally affect the outcome
    AND (b) actually changed during the detected fault — suppressing variables
    with large structural coefficients that did not change (e.g. vibration).

    Falls back to Pearson-correlation-based estimates when DoWhy is unavailable
    or fails; method field records which path was taken.
    """
    df = pd.DataFrame(rows).select_dtypes(include="number").fillna(0)
    if df.empty or len(df.columns) < 2:
        return []

    # Drop row-index / timestamp columns (monotone integers 0..N-1)
    index_cols = [
        c for c in df.columns
        if df[c].is_monotonic_increasing
        and df[c].min() == 0
        and df[c].diff().dropna().eq(1).all()
    ]
    df = df.drop(columns=index_cols)

    # Auto-select outcome if not supplied
    if outcome_col is None or outcome_col not in df.columns:
        outcome_col = df.var().idxmax()

    treatments = [c for c in df.columns if c != outcome_col]

    # Pre-compute fault-window deltas when anomaly context is available
    if anomaly_indices:
        normal_idx = [i for i in range(len(df)) if i not in anomaly_indices]
        normal_mean = df.iloc[normal_idx].mean()
        fault_mean = df.iloc[list(anomaly_indices)].mean()
        deltas = {c: abs(float(fault_mean[c] - normal_mean[c])) for c in df.columns}
    else:
        deltas = {c: 1.0 for c in df.columns}  # no delta info — use raw effect

    # Build dot-format graph string for DoWhy
    if causal_graph:
        edges = [
            f"{parent} -> {child}"
            for parent, children in causal_graph.items()
            for child in children
        ]
        graph_dot = "digraph { " + "; ".join(edges) + " }" if edges else None
    else:
        graph_dot = None

    results = []

    for treatment in treatments:
        if not DOWHY_AVAILABLE:
            corr = float(df[treatment].corr(df[outcome_col]))
            raw_effect = abs(corr)
            method = "correlation"
        else:
            try:
                model = CausalModel(
                    data=df,
                    treatment=treatment,
                    outcome=outcome_col,
                    graph=graph_dot,
                )
                identified = model.identify_effect(proceed_when_unidentifiable=True)
                estimate = model.estimate_effect(
                    identified,
                    method_name="backdoor.linear_regression",
                )
                raw_effect = abs(float(estimate.value)) if estimate.value is not None else 0.0
                method = "dowhy"
            except Exception:
                corr = float(df[treatment].corr(df[outcome_col]))
                raw_effect = abs(corr)
                method = "correlation_fallback"

        delta = deltas.get(treatment, 1.0)
        effect_size = raw_effect * delta  # anomaly contribution (or raw if no delta)

        results.append({
            "feature":      treatment,
            "effect_size":  round(effect_size, 6),
            "raw_effect":   round(raw_effect, 6),
            "delta":        round(delta, 6),
            "confidence":   round(min(effect_size / (effect_size + 1), 1.0), 6),
            "method":       method,
        })

    return sorted(results, key=lambda x: x["effect_size"], reverse=True)
