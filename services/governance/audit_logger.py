from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rca_user:rca_pass@localhost:5432/rca_platform",
)

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def write_audit(
    audit_id: str,
    trace_id: str,
    service: str,
    event_type: str,
    payload: Dict[str, Any],
    timestamp: datetime,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log (audit_id, trace_id, service, event_type, payload, timestamp)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6)
            ON CONFLICT (audit_id) DO NOTHING
            """,
            audit_id,
            trace_id,
            service,
            event_type,
            json.dumps(payload),
            timestamp,
        )


async def query_audit(
    trace_id: Optional[str],
    service: Optional[str],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
    limit: int,
) -> List[Dict[str, Any]]:
    pool = await get_pool()
    clauses = []
    params: list = []
    idx = 1

    if trace_id:
        clauses.append(f"trace_id = ${idx}")
        params.append(trace_id)
        idx += 1
    if service:
        clauses.append(f"service = ${idx}")
        params.append(service)
        idx += 1
    if from_dt:
        clauses.append(f"timestamp >= ${idx}")
        params.append(from_dt)
        idx += 1
    if to_dt:
        clauses.append(f"timestamp <= ${idx}")
        params.append(to_dt)
        idx += 1

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    rows = await pool.fetch(
        f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ${idx}",
        *params,
    )
    return [dict(r) for r in rows]
