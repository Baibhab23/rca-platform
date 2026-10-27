from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests


def test_causality(
    rows: List[Dict[str, Any]],
    max_lag: int = 3,
    p_threshold: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    Run pairwise Granger causality tests on all numeric feature pairs.
    Returns features that Granger-cause the target (highest-variance column).
    Result format: {feature, effect_size, confidence, method}.
    """
    df = pd.DataFrame(rows).select_dtypes(include="number").ffill().fillna(0)
    if df.empty or len(df) < max_lag * 3 or len(df.columns) < 2:
        return []

    target = df.var().idxmax()
    results = []

    for col in df.columns:
        if col == target:
            continue
        try:
            test_data = df[[target, col]].dropna()
            if len(test_data) < max_lag * 3:
                continue
            test_result = grangercausalitytests(test_data, maxlag=max_lag, verbose=False)
            min_p = min(
                test_result[lag][0]["ssr_chi2test"][1]
                for lag in range(1, max_lag + 1)
            )
            if min_p < p_threshold:
                results.append({
                    "feature": col,
                    "effect_size": 1.0 - min_p,
                    "confidence": 1.0 - min_p,
                    "method": "granger",
                })
        except Exception:
            continue

    return sorted(results, key=lambda x: x["confidence"], reverse=True)
