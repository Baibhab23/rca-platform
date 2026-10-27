from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def detect(
    rows: List[Dict[str, Any]],
    threshold: float = 3.0,
) -> Tuple[List[int], List[float], List[str]]:
    """
    Univariate Z-score detector. Flags rows where ANY numeric feature
    has |z| > threshold.
    Returns (anomaly_indices, max_z_per_row, numeric_features).
    """
    df = pd.DataFrame(rows).select_dtypes(include="number").fillna(0)
    if df.empty or len(df) < 2:
        return [], [], []

    features = df.columns.tolist()
    z_scores = (df - df.mean()) / (df.std().replace(0, 1))
    max_z = z_scores.abs().max(axis=1)

    anomaly_indices = max_z[max_z > threshold].index.tolist()
    return anomaly_indices, max_z.tolist(), features
