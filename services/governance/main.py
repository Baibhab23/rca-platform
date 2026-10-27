from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.environ.get("RCA_PROJECT_ROOT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "../..")))

from fastapi import FastAPI, Query
from pydantic import BaseModel

from shared.events import ALL_EVENTS
from shared.redis_bus import subscribe
from shared.schemas import AuditEvent
from audit_logger import query_audit, write_audit

app = FastAPI(title="Governance Service", version="1.0.0")

SERVICE_MAP = {
    "data.ingested": "ingestion",
    "anomaly.detected": "anomaly",
    "rca.complete": "rca",
    "prescription.ready": "prescriptive",
    "narrative.generated": "narrative",
}


async def _handle_event(channel: str, payload: Dict[str, Any]) -> None:
    event = AuditEvent(
        trace_id=payload.get("trace_id", "unknown"),
        service=SERVICE_MAP.get(channel, channel),
        event_type=channel,
        payload=payload,
    )
    await write_audit(
        audit_id=event.audit_id,
        trace_id=event.trace_id,
        service=event.service,
        event_type=event.event_type,
        payload=event.payload,
        timestamp=event.timestamp,
    )


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(subscribe(ALL_EVENTS, _handle_event))


@app.get("/audit")
async def get_audit(
    trace_id: Optional[str] = Query(None),
    service: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    limit: int = Query(100, ge=1, le=1000),
) -> List[Dict[str, Any]]:
    return await query_audit(trace_id, service, from_dt, to_dt, limit)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "governance"}
