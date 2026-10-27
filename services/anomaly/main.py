from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.events import DATA_INGESTED, ANOMALY_DETECTED
from shared.redis_bus import publish, subscribe
from shared.schemas import AnomalyResult, IngestedData, AnalysisResponse

from detectors import isolation_forest, zscore, lstm_detector

app = FastAPI(title="Anomaly Detection Service", version="1.0.0")


class DetectRequest(BaseModel):
    trace_id: str
    rows: List[Dict[str, Any]]
    method: str = "isolation_forest"  # "isolation_forest" | "zscore" | "lstm"
    threshold: float = 3.0
    contamination: float = 0.05


def _run_detection(
    rows: List[Dict[str, Any]],
    method: str,
    threshold: float,
    contamination: float,
) -> tuple[List[int], List[float], List[str]]:
    if method == "zscore":
        return zscore.detect(rows, threshold=threshold)
    if method == "lstm":
        return lstm_detector.detect(rows)
    return isolation_forest.detect(rows, contamination=contamination)


async def _process_ingested(channel: str, payload: Dict[str, Any]) -> None:
    data = IngestedData(**payload)
    method = "isolation_forest"
    indices, scores, features = _run_detection(data.rows, method, 3.0, 0.05)

    if not indices:
        return

    result = AnomalyResult(
        trace_id=data.trace_id,
        method=method,
        anomalous_rows=[data.rows[i] for i in indices],
        scores=[scores[i] for i in indices],
        features=features,
        threshold=0.05,
    )
    await publish(ANOMALY_DETECTED, result.model_dump(mode="json"))


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(subscribe([DATA_INGESTED], _process_ingested))


@app.post("/detect", response_model=AnomalyResult)
async def detect(request: DetectRequest) -> AnomalyResult:
    indices, scores, features = _run_detection(
        request.rows, request.method, request.threshold, request.contamination
    )
    if not indices:
        raise HTTPException(404, "No anomalies detected")

    result = AnomalyResult(
        trace_id=request.trace_id,
        method=request.method,
        anomalous_rows=[request.rows[i] for i in indices],
        scores=[scores[i] for i in indices],
        features=features,
        threshold=request.threshold,
    )
    await publish(ANOMALY_DETECTED, result.model_dump(mode="json"))
    return result


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "anomaly"}
