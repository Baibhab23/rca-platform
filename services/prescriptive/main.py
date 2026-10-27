from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.events import RCA_COMPLETE, PRESCRIPTION_READY
from shared.redis_bus import publish, subscribe
from shared.schemas import RCAResult, PrescriptionResult, Action

from optimizers import pulp_optimizer, recommender

app = FastAPI(title="Prescriptive Service", version="1.0.0")


class PrescribeRequest(BaseModel):
    rca_id: str
    trace_id: str
    root_causes: List[Dict[str, Any]]
    budget: float = 1.0


def _run_prescription(
    root_causes: List[Dict[str, Any]],
    rca_id: str,
    trace_id: str,
    budget: float = 1.0,
) -> PrescriptionResult:
    cause_dicts = [rc if isinstance(rc, dict) else rc.model_dump() for rc in root_causes]
    optimized = pulp_optimizer.optimize(cause_dicts, budget=budget)

    if not optimized:
        optimized = cause_dicts[:3]  # fallback: top-3 by effect_size

    raw_actions = recommender.generate_actions(optimized)
    actions = [Action(**a) for a in raw_actions]

    return PrescriptionResult(
        rca_id=rca_id,
        trace_id=trace_id,
        actions=actions,
        optimization_status="optimal" if optimized else "fallback",
    )


async def _handle_rca(channel: str, payload: Dict[str, Any]) -> None:
    rca = RCAResult(**payload)
    if not rca.root_causes:
        return
    cause_dicts = [rc.model_dump() for rc in rca.root_causes]
    result = _run_prescription(cause_dicts, rca.rca_id, rca.trace_id)
    await publish(PRESCRIPTION_READY, result.model_dump(mode="json"))


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(subscribe([RCA_COMPLETE], _handle_rca))


@app.post("/prescribe", response_model=PrescriptionResult)
async def prescribe(request: PrescribeRequest) -> PrescriptionResult:
    if not request.root_causes:
        raise HTTPException(400, "root_causes cannot be empty")
    result = _run_prescription(
        request.root_causes, request.rca_id, request.trace_id, request.budget
    )
    await publish(PRESCRIPTION_READY, result.model_dump(mode="json"))
    return result


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "prescriptive"}
