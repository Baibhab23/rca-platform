"""Thin async Redis pub/sub wrapper used by all services."""
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Callable, Dict

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


def _get_client() -> aioredis.Redis:
    return aioredis.from_url(REDIS_URL, decode_responses=True)


async def publish(channel: str, payload: Dict[str, Any]) -> None:
    client = _get_client()
    try:
        await client.publish(channel, json.dumps(payload))
    finally:
        await client.aclose()


async def subscribe(channels: list[str], handler: Callable[[str, Dict[str, Any]], Any]) -> None:
    """Block and dispatch messages to handler(channel, payload)."""
    client = _get_client()
    pubsub = client.pubsub()
    await pubsub.subscribe(*channels)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"]
                payload = json.loads(message["data"])
                await handler(channel, payload)
    finally:
        await pubsub.unsubscribe(*channels)
        await client.aclose()
