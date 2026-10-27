from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


async def fetch_data(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Fetch data from a REST API endpoint, returning a list of record dicts."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=method.upper(),
            url=url,
            headers=headers or {},
            params=params,
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "records", "results", "items", "rows"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    raise ValueError(f"Unexpected REST response shape: {type(data)}")
