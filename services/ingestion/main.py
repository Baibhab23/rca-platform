from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, HTTPException

from shared.events import DATA_INGESTED
from shared.redis_bus import publish
from shared.schemas import IngestRequest, IngestedData, AnalysisResponse

from connectors import postgres, rest_api, kafka_source

app = FastAPI(title="Ingestion Service", version="1.0.0")


def _normalize(rows: List[Dict[str, Any]]) -> tuple[List[str], List[Dict[str, Any]]]:
    if not rows:
        return [], []
    columns = list(rows[0].keys())
    return columns, rows


@app.post("/ingest", response_model=AnalysisResponse)
async def ingest(request: IngestRequest) -> AnalysisResponse:
    rows: List[Dict[str, Any]] = []

    if request.source_type == "postgres":
        if not request.query:
            raise HTTPException(400, "SQL query required for postgres source")
        rows = await postgres.fetch_data(request.connection, request.query)

    elif request.source_type == "rest":
        url = request.connection.get("url") or request.query
        if not url:
            raise HTTPException(400, "url required for REST source")
        rows = await rest_api.fetch_data(
            url=url,
            method=request.connection.get("method", "GET"),
            headers=request.connection.get("headers"),
            body=request.connection.get("body"),
            params=request.connection.get("params"),
        )

    elif request.source_type == "kafka":
        topic = request.query or request.connection.get("topic")
        if not topic:
            raise HTTPException(400, "topic required for kafka source")
        rows = kafka_source.consume_messages(
            topic=topic,
            group_id=request.connection.get("group_id", "rca-ingestion"),
            max_messages=request.connection.get("max_messages", 1000),
        )

    else:
        raise HTTPException(400, f"Unknown source_type: {request.source_type}")

    columns, normalized_rows = _normalize(rows)
    payload = IngestedData(
        trace_id=request.trace_id,
        source_type=request.source_type,
        columns=columns,
        rows=normalized_rows,
    )
    await publish(DATA_INGESTED, payload.model_dump(mode="json"))

    return AnalysisResponse(
        trace_id=request.trace_id,
        status="ingested",
        message=f"Ingested {len(rows)} rows from {request.source_type}",
    )


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
