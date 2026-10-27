from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid4())


# ── Ingestion ──────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    source_type: str  # "postgres" | "rest" | "kafka"
    connection: Dict[str, Any]
    query: Optional[str] = None          # SQL query or REST URL or Kafka topic
    extra: Optional[Dict[str, Any]] = None
    trace_id: str = Field(default_factory=_uuid)


class IngestedData(BaseModel):
    trace_id: str
    source_type: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ── Anomaly ────────────────────────────────────────────────────────────────────

class AnomalyResult(BaseModel):
    anomaly_id: str = Field(default_factory=_uuid)
    trace_id: str
    method: str                          # "isolation_forest" | "zscore" | "lstm"
    anomalous_rows: List[Dict[str, Any]]
    scores: List[float]
    features: List[str]
    threshold: float
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ── RCA ────────────────────────────────────────────────────────────────────────

class RootCause(BaseModel):
    feature: str
    effect_size: float
    confidence: float
    method: str  # "dowhy" | "granger" | "correlation"


class RCAResult(BaseModel):
    rca_id: str = Field(default_factory=_uuid)
    anomaly_id: str
    trace_id: str
    root_causes: List[RootCause]
    causal_graph: Dict[str, List[str]]   # adjacency list  {node: [children]}
    summary: str
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Prescriptive ───────────────────────────────────────────────────────────────

class Action(BaseModel):
    action_id: str = Field(default_factory=_uuid)
    description: str
    target_feature: str
    adjustment: Any
    expected_impact: float               # 0-1 normalized
    priority: int                        # lower = higher priority


class PrescriptionResult(BaseModel):
    prescription_id: str = Field(default_factory=_uuid)
    rca_id: str
    trace_id: str
    actions: List[Action]
    optimization_status: str
    prescribed_at: datetime = Field(default_factory=datetime.utcnow)


# ── Narrative ──────────────────────────────────────────────────────────────────

class NarrativeResult(BaseModel):
    narrative_id: str = Field(default_factory=_uuid)
    prescription_id: str
    trace_id: str
    summary: str
    explanation: str
    recommendations: List[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Governance ─────────────────────────────────────────────────────────────────

class AuditEvent(BaseModel):
    audit_id: str = Field(default_factory=_uuid)
    trace_id: str
    service: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Gateway API response ────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    trace_id: str
    status: str
    message: str
