from __future__ import annotations

from typing import Any, Dict, List

import asyncpg
import pandas as pd


async def fetch_data(
    connection_config: Dict[str, Any],
    query: str,
) -> List[Dict[str, Any]]:
    """Execute a SELECT query against PostgreSQL and return rows as dicts."""
    dsn = connection_config.get("dsn") or (
        f"postgresql://{connection_config['user']}:{connection_config['password']}"
        f"@{connection_config['host']}:{connection_config.get('port', 5432)}"
        f"/{connection_config['database']}"
    )
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(query)
        return [dict(r) for r in rows]
    finally:
        await conn.close()
