from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional
from uuid import uuid4

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from middleware.auth import authenticate, create_token, verify_token
from shared.schemas import IngestRequest, AnalysisResponse

app = FastAPI(title="RCA Platform API Gateway", version="1.0.0")

INGESTION_URL    = os.getenv("INGESTION_URL",    "http://ingestion:8001")
ANOMALY_URL      = os.getenv("ANOMALY_URL",      "http://anomaly:8002")
RCA_URL          = os.getenv("RCA_URL",          "http://rca:8003")
PRESCRIPTIVE_URL = os.getenv("PRESCRIPTIVE_URL", "http://prescriptive:8004")
NARRATIVE_URL    = os.getenv("NARRATIVE_URL",    "http://narrative:8005")
GOVERNANCE_URL   = os.getenv("GOVERNANCE_URL",   "http://governance:8006")


# ── Auth ───────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/token")
async def login(request: LoginRequest) -> Dict[str, str]:
    if not authenticate(request.username, request.password):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": create_token(request.username), "token_type": "bearer"}


# ── Full pipeline trigger ──────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(
    request: IngestRequest,
    _: str = Depends(verify_token),
) -> AnalysisResponse:
    """Trigger the full pipeline: ingest → detect → RCA → prescribe → narrate."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{INGESTION_URL}/ingest",
            json=request.model_dump(mode="json"),
        )
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text)
    return AnalysisResponse(
        trace_id=request.trace_id,
        status="pipeline_triggered",
        message="Ingestion complete; anomaly detection, RCA, and prescription running asynchronously.",
    )


# ── Direct service endpoints ───────────────────────────────────────────────────

@app.post("/detect")
async def detect(
    body: Dict[str, Any],
    _: str = Depends(verify_token),
) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{ANOMALY_URL}/detect", json=body)
        resp.raise_for_status()
    return resp.json()


@app.post("/rca")
async def rca(
    body: Dict[str, Any],
    _: str = Depends(verify_token),
) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{RCA_URL}/analyze", json=body)
        resp.raise_for_status()
    return resp.json()


@app.post("/prescribe")
async def prescribe(
    body: Dict[str, Any],
    _: str = Depends(verify_token),
) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{PRESCRIPTIVE_URL}/prescribe", json=body)
        resp.raise_for_status()
    return resp.json()


@app.post("/narrate")
async def narrate(
    body: Dict[str, Any],
    _: str = Depends(verify_token),
) -> Any:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{NARRATIVE_URL}/narrate", json=body)
        resp.raise_for_status()
    return resp.json()


@app.get("/audit")
async def audit(
    trace_id: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    from_dt: Optional[str] = Query(None, alias="from"),
    to_dt: Optional[str] = Query(None, alias="to"),
    limit: int = Query(100),
    _: str = Depends(verify_token),
) -> Any:
    params: Dict[str, Any] = {"limit": limit}
    if trace_id:
        params["trace_id"] = trace_id
    if service:
        params["service"] = service
    if from_dt:
        params["from"] = from_dt
    if to_dt:
        params["to"] = to_dt

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{GOVERNANCE_URL}/audit", params=params)
        resp.raise_for_status()
    return resp.json()


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> Dict[str, Any]:
    services = {
        "ingestion": INGESTION_URL,
        "anomaly": ANOMALY_URL,
        "rca": RCA_URL,
        "prescriptive": PRESCRIPTIVE_URL,
        "narrative": NARRATIVE_URL,
        "governance": GOVERNANCE_URL,
    }
    statuses: Dict[str, str] = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in services.items():
            try:
                r = await client.get(f"{url}/health")
                statuses[name] = "ok" if r.status_code == 200 else "degraded"
            except Exception:
                statuses[name] = "unreachable"
    overall = "ok" if all(v == "ok" for v in statuses.values()) else "degraded"
    return {"status": overall, "services": statuses}
