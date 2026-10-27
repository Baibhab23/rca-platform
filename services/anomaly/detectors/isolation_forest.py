from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def detect(
    rows: List[Dict[str, Any]],
    contamination: float = 0.05,
    random_state: int = 42,
) -> Tuple[List[int], List[float], List[str]]:
    """
    Returns (anomaly_indices, scores, numeric_features).
    Score is the raw anomaly score (more negative = more anomalous).
    """
    df = pd.DataFrame(rows).select_dtypes(include="number")
    if df.empty or len(df) < 2:
        return [], [], []

    features = df.columns.tolist()
    X = df.fillna(df.median()).values

    clf = IsolationForest(contamination=contamination, random_state=random_state)
    labels = clf.fit_predict(X)          # -1 = anomaly, 1 = normal
    scores = clf.score_samples(X).tolist()

    anomaly_indices = [i for i, lbl in enumerate(labels) if lbl == -1]
    return anomaly_indices, scores, features
