from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class _LSTMAutoEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 32) -> None:
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        self.decoder = nn.LSTM(hidden_dim, input_dim, batch_first=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h, _) = self.encoder(x)
        h_repeated = h.permute(1, 0, 2).repeat(1, x.size(1), 1)
        out, _ = self.decoder(h_repeated)
        return out


def detect(
    rows: List[Dict[str, Any]],
    seq_len: int = 10,
    hidden_dim: int = 32,
    epochs: int = 20,
    threshold_factor: float = 2.5,
) -> Tuple[List[int], List[float], List[str]]:
    """
    LSTM autoencoder for time-series reconstruction-error anomaly detection.
    Trains on-the-fly per batch (suitable for small-to-medium datasets).
    """
    df = pd.DataFrame(rows).select_dtypes(include="number").fillna(0)
    if df.empty or len(df) < seq_len + 1:
        return [], [], []

    features = df.columns.tolist()
    data = torch.tensor(df.values, dtype=torch.float32)
    data = (data - data.mean(0)) / (data.std(0) + 1e-8)  # normalize

    sequences = torch.stack(
        [data[i : i + seq_len] for i in range(len(data) - seq_len)]
    )  # (N, seq_len, features)

    model = _LSTMAutoEncoder(len(features), hidden_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        out = model(sequences)
        loss = criterion(out, sequences)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        recon = model(sequences)
        errors = ((recon - sequences) ** 2).mean(dim=(1, 2)).numpy()

    threshold = errors.mean() + threshold_factor * errors.std()
    anomaly_seq_indices = np.where(errors > threshold)[0].tolist()

    # Map sequence start index back to row index (use the last row of each seq)
    anomaly_row_indices = sorted({i + seq_len - 1 for i in anomaly_seq_indices})

    # Pad scores array to match original row count (non-seq rows get score 0)
    full_scores = [0.0] * len(rows)
    for i, score in enumerate(errors.tolist()):
        full_scores[i + seq_len - 1] = float(score)

    return anomaly_row_indices, full_scores, features
