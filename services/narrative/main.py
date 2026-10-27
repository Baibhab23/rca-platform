from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.events import PRESCRIPTION_READY, NARRATIVE_GENERATED
from shared.redis_bus import publish, subscribe
from shared.schemas import PrescriptionResult, NarrativeResult, RCAResult

import claude_client

app = FastAPI(title="Narrative Service", version="1.0.0")


class NarrateRequest(BaseModel):
    prescription_id: str
    trace_id: str
    rca_summary: str
    root_causes: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]


async def _handle_prescription(channel: str, payload: Dict[str, Any]) -> None:
    prescription = PrescriptionResult(**payload)
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: claude_client.generate_narrative(
            prescription=payload,
            rca_summary=payload.get("rca_summary", "Anomaly detected in dataset."),
            root_causes=payload.get("root_causes", []),
        ),
    )

    narrative = NarrativeResult(
        prescription_id=prescription.prescription_id,
        trace_id=prescription.trace_id,
        summary=result["summary"],
        explanation=result["explanation"],
        recommendations=result["recommendations"],
    )
    await publish(NARRATIVE_GENERATED, narrative.model_dump(mode="json"))


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(subscribe([PRESCRIPTION_READY], _handle_prescription))


@app.post("/narrate", response_model=NarrativeResult)
async def narrate(request: NarrateRequest) -> NarrativeResult:
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: claude_client.generate_narrative(
            prescription={"actions": request.actions},
            rca_summary=request.rca_summary,
            root_causes=request.root_causes,
        ),
    )
    narrative = NarrativeResult(
        prescription_id=request.prescription_id,
        trace_id=request.trace_id,
        summary=result["summary"],
        explanation=result["explanation"],
        recommendations=result["recommendations"],
    )
    await publish(NARRATIVE_GENERATED, narrative.model_dump(mode="json"))
    return narrative


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "narrative"}
