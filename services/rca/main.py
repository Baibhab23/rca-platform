from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.events import ANOMALY_DETECTED, RCA_COMPLETE
from shared.redis_bus import publish, subscribe
from shared.schemas import AnomalyResult, RCAResult, RootCause

from engines import causal_graph, dowhy_engine, granger

app = FastAPI(title="RCA Service", version="1.0.0")


class RCARequest(BaseModel):
    anomaly_id: str
    trace_id: str
    rows: List[Dict[str, Any]]


def _run_rca(
    rows: List[Dict[str, Any]],
    anomaly_id: str,
    trace_id: str,
) -> RCAResult:
    graph = causal_graph.build_graph(rows)
    causal_effects = dowhy_engine.estimate_effects(rows, graph)
    granger_causes = granger.test_causality(rows)

    # Merge results, deduplicating by feature, preferring DoWhy
    seen: Dict[str, Dict[str, Any]] = {}
    for item in causal_effects + granger_causes:
        feat = item["feature"]
        if feat not in seen or item["confidence"] > seen[feat]["confidence"]:
            seen[feat] = item

    root_causes = [
        RootCause(
            feature=v["feature"],
            effect_size=v["effect_size"],
            confidence=v["confidence"],
            method=v["method"],
        )
        for v in sorted(seen.values(), key=lambda x: x["confidence"], reverse=True)
    ]

    top = root_causes[0].feature if root_causes else "unknown"
    summary = (
        f"Top root cause: '{top}' with confidence "
        f"{root_causes[0].confidence:.2f}. "
        f"Identified {len(root_causes)} contributing factors."
        if root_causes else "No significant root causes found."
    )

    return RCAResult(
        anomaly_id=anomaly_id,
        trace_id=trace_id,
        root_causes=root_causes[:10],
        causal_graph=graph,
        summary=summary,
    )


async def _handle_anomaly(channel: str, payload: Dict[str, Any]) -> None:
    anomaly = AnomalyResult(**payload)
    if not anomaly.anomalous_rows:
        return
    result = _run_rca(anomaly.anomalous_rows, anomaly.anomaly_id, anomaly.trace_id)
    await publish(RCA_COMPLETE, result.model_dump(mode="json"))


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(subscribe([ANOMALY_DETECTED], _handle_anomaly))


@app.post("/analyze", response_model=RCAResult)
async def analyze(request: RCARequest) -> RCAResult:
    if not request.rows:
        raise HTTPException(400, "rows cannot be empty")
    result = _run_rca(request.rows, request.anomaly_id, request.trace_id)
    await publish(RCA_COMPLETE, result.model_dump(mode="json"))
    return result


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "rca"}
