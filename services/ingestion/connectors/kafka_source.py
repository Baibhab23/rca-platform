from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Dict, List

from confluent_kafka import Consumer, KafkaError, KafkaException

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


def consume_messages(
    topic: str,
    group_id: str = "rca-ingestion",
    max_messages: int = 1000,
    timeout_seconds: float = 10.0,
) -> List[Dict[str, Any]]:
    """
    Consume up to max_messages from a Kafka topic (synchronous batch read).
    Returns a list of parsed JSON records.
    """
    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    }
    consumer = Consumer(conf)
    consumer.subscribe([topic])

    records: List[Dict[str, Any]] = []
    idle_count = 0
    max_idle = 3

    try:
        while len(records) < max_messages and idle_count < max_idle:
            msg = consumer.poll(timeout=timeout_seconds)
            if msg is None:
                idle_count += 1
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    idle_count += 1
                    continue
                raise KafkaException(msg.error())
            idle_count = 0
            value = msg.value()
            if value:
                try:
                    records.append(json.loads(value.decode("utf-8")))
                except json.JSONDecodeError:
                    records.append({"raw": value.decode("utf-8")})
    finally:
        consumer.close()

    return records
