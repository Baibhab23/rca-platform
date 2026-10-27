from __future__ import annotations

from typing import Any, Dict, List

import networkx as nx
import pandas as pd


def build_graph(rows: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Build a causal DAG from correlation structure using a simple
    threshold-based approach. Returns an adjacency list {node: [children]}.
    Uses Pearson correlation with a 0.3 threshold as a proxy for causal edges.
    """
    df = pd.DataFrame(rows).select_dtypes(include="number").fillna(0)
    if df.empty or len(df.columns) < 2:
        return {}

    corr = df.corr().abs()
    G = nx.DiGraph()
    G.add_nodes_from(df.columns)

    # Add directed edges from higher-variance to lower-variance features
    variances = df.var()
    cols = df.columns.tolist()
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if corr.loc[a, b] >= 0.3:
                parent = a if variances[a] >= variances[b] else b
                child = b if parent == a else a
                if not nx.has_path(G, child, parent):  # avoid cycles
                    G.add_edge(parent, child)

    return {node: list(G.successors(node)) for node in G.nodes}
