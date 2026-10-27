# RCA Platform

An end-to-end, event-driven microservices platform that automatically detects anomalies in operational data, identifies their root causes using causal inference, prescribes prioritised remediation actions, and delivers the findings as plain-English business narratives via Claude AI.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Experiment Results](#experiment-results)
- [Configuration](#configuration)

---

## Overview

Most observability tools tell you *that* something went wrong. This platform tells you *why* — and then tells you *what to do about it*, in a language your operations team can act on.

The pipeline runs in five stages, each as an independent microservice communicating over Redis pub/sub:

```
Ingest → Detect Anomalies → Root Cause Analysis → Prescribe Actions → Generate Narrative
```

Each stage can be triggered via the unified API gateway, or fired independently for targeted use. Every event is persisted to an audit log in Postgres for traceability.

---

## Architecture

```mermaid
flowchart TD
    subgraph EXT["External Sources"]
        OA[Oracle APEX]
        SF[Salesforce]
        SAP[SAP BTP]
    end

    GW["**Gateway Service** :8000\nJWT auth · routing"]

    ING["**Ingestion Service** :8001\nPostgreSQL · REST · Kafka"]
    ANO["**Anomaly Service** :8002\nZ-Score · Isolation Forest · LSTM"]
    RCA["**RCA Service** :8003\nCausal Graph · DoWhy · Granger"]
    PRE["**Prescriptive Service** :8004\nLP Optimiser · PuLP/CBC"]
    NAR["**Narrative Service** :8005\nClaude claude-sonnet-4-6"]
    GOV[("**Governance Service** :8006\nPostgreSQL audit log")]

    OA --> GW
    SF --> GW
    SAP --> GW

    GW --> ING
    ING -->|data.ingested| ANO
    ANO -->|anomaly.detected| RCA
    RCA -->|rca.complete| PRE
    PRE -->|prescription.ready| NAR

    ING -.->|audit| GOV
    ANO -.->|audit| GOV
    RCA -.->|audit| GOV
    PRE -.->|audit| GOV
    NAR -.->|audit| GOV
```

Solid arrows are Redis pub/sub events driving the pipeline forward.
Dashed arrows show every service also writing to the Governance audit log.

---

## Services

### Gateway (`services/gateway`)
Single entry point for all external traffic. Handles JWT authentication, routes requests to the appropriate downstream service, and exposes a `/health` endpoint that aggregates the health of all six backend services.

### Ingestion (`services/ingestion`)
Pulls raw data from three source types:
- **PostgreSQL** — SQL query over a configured connection string
- **REST API** — HTTP GET with configurable headers
- **Kafka** — topic consumer with configurable offset

Normalises all data into a common row format and publishes the `data_ingested` event.

### Anomaly Detection (`services/anomaly`)
Three interchangeable detectors, selectable per request:

| Detector | Method | Best for |
|---|---|---|
| **Z-Score** | Flags rows where any numeric feature exceeds ±N standard deviations | Fast, interpretable, real-time alerting |
| **Isolation Forest** | Ensemble of random trees; short average path = anomaly | Multivariate, no distribution assumptions |
| **LSTM Autoencoder** | Trains on sequences, flags high reconstruction error | Temporal patterns, gradual drift |

The service defaults to Isolation Forest for event-driven processing, and exposes all three via the `/detect` endpoint.

### Root Cause Analysis (`services/rca`)
Runs three complementary causal analyses and merges results by confidence, deduplicating by feature:

1. **Causal Graph** — builds a DAG from correlation structure (Pearson ≥ 0.3, variance-directed edges, cycle prevention via NetworkX)
2. **DoWhy** — estimates causal effects using backdoor linear regression on the DAG; falls back to Pearson correlation when DoWhy is unavailable
3. **Granger Causality** — pairwise chi-squared tests (statsmodels) to find features with statistically significant lagged predictive power (p < 0.05)

Effect sizes are weighted by the delta between the fault window and the normal baseline, so variables that causally matter *and* actually changed during the fault rank highest.

### Prescriptive Analytics (`services/prescriptive`)
Frames intervention selection as a **0/1 knapsack problem** solved with PuLP/CBC:

- **Objective:** maximise `Σ(effect_size × confidence)` across selected actions
- **Constraint:** normalised resource cost stays within a configurable budget fraction
- Falls back to top-3 by effect size if the LP finds no feasible solution

### Narrative Generation (`services/narrative`)
Calls the Anthropic API (claude-sonnet-4-6) with the full pipeline output and generates:
- An executive summary (2–3 sentences)
- A root cause explanation in business terms
- 3–5 prioritised, actionable recommendations

Uses **prompt caching** on the system prompt to reduce latency and token cost on repeated calls.

### Governance (`services/governance`)
Persists every pipeline event to Postgres as a structured audit record. Queryable by `trace_id`, `service`, or time range via the gateway's `/audit` endpoint.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Pydantic v2 |
| Async runtime | asyncio + uvicorn |
| Messaging | Redis pub/sub |
| Streaming ingest | Apache Kafka |
| Storage | PostgreSQL 15 |
| ML / anomaly | scikit-learn, PyTorch |
| Causal inference | DoWhy, statsmodels (Granger) |
| Graph analysis | NetworkX |
| Optimisation | PuLP (CBC solver) |
| AI narrative | Anthropic SDK (Claude) |
| Containerisation | Docker Compose |
| Schema validation | Pydantic v2 |

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- An Anthropic API key (for the narrative service)

### 1. Clone and configure

```bash
git clone https://github.com/Baibhab23/rca-platform.git
cd rca-platform
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 2. Start all services

```bash
./start.sh
# or: docker compose up --build
```

This starts Postgres, Redis, Kafka/Zookeeper, and all seven application services.

### 3. Try the API with Bruno

The collection below covers all eight endpoints. Open [Bruno](https://www.usebruno.com/), create a new collection, add a **Local** environment with `baseUrl = http://localhost:8000` and `token = <empty>`, then paste each block as a new request.

> Run **Get Token** first and copy the `access_token` into the `token` environment variable — every other request picks it up automatically via `{{token}}`.

---

**Health Check**
```
meta {
  name: Health Check
  type: http
  seq: 1
}

get {
  url: {{baseUrl}}/health
  body: none
  auth: none
}
```

---

**Get Token**
```
meta {
  name: Get Token
  type: http
  seq: 2
}

post {
  url: {{baseUrl}}/auth/token
  body: json
  auth: none
}

body:json {
  {
    "username": "admin",
    "password": "admin"
  }
}
```

---

**Full Pipeline** *(triggers the full async pipeline — poll Audit Log to follow progress)*
```
meta {
  name: Full Pipeline
  type: http
  seq: 3
}

post {
  url: {{baseUrl}}/analyze
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "source_type": "rest",
    "connection": {
      "url": "https://your-data-endpoint.example.com/metrics"
    },
    "trace_id": "demo-001"
  }
}
```

---

**Detect Anomalies** *(method: `isolation_forest` | `zscore` | `lstm`)*
```
meta {
  name: Detect Anomalies
  type: http
  seq: 4
}

post {
  url: {{baseUrl}}/detect
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "trace_id": "demo-001",
    "method": "isolation_forest",
    "contamination": 0.05,
    "rows": [
      {"temperature": 75.1, "pressure": 100.2, "vibration": 0.50, "flow_rate": 50.1, "output_quality": 96.2},
      {"temperature": 74.8, "pressure":  99.8, "vibration": 0.49, "flow_rate": 49.8, "output_quality": 95.9},
      {"temperature": 95.4, "pressure":  68.3, "vibration": 0.51, "flow_rate": 49.5, "output_quality": 71.3},
      {"temperature": 96.1, "pressure":  65.7, "vibration": 0.52, "flow_rate": 49.2, "output_quality": 69.8},
      {"temperature": 75.3, "pressure": 100.5, "vibration": 0.50, "flow_rate": 50.3, "output_quality": 96.4}
    ]
  }
}
```

---

**Root Cause Analysis** *(pass the anomalous rows returned by Detect)*
```
meta {
  name: Root Cause Analysis
  type: http
  seq: 5
}

post {
  url: {{baseUrl}}/rca
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "anomaly_id": "replace-with-anomaly-id",
    "trace_id": "demo-001",
    "rows": [
      {"temperature": 95.4, "pressure": 68.3, "vibration": 0.51, "flow_rate": 49.5, "output_quality": 71.3},
      {"temperature": 96.1, "pressure": 65.7, "vibration": 0.52, "flow_rate": 49.2, "output_quality": 69.8},
      {"temperature": 95.8, "pressure": 67.1, "vibration": 0.50, "flow_rate": 49.8, "output_quality": 70.5}
    ]
  }
}
```

---

**Prescribe Actions** *(budget: fraction of total resource budget to spend, 0.0 – 1.0)*
```
meta {
  name: Prescribe Actions
  type: http
  seq: 6
}

post {
  url: {{baseUrl}}/prescribe
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "rca_id": "replace-with-rca-id",
    "trace_id": "demo-001",
    "budget": 0.6,
    "root_causes": [
      {"feature": "temperature", "effect_size": 17.241, "confidence": 0.945, "method": "correlation"},
      {"feature": "pressure",    "effect_size":  5.632, "confidence": 0.849, "method": "correlation"},
      {"feature": "vibration",   "effect_size":  0.396, "confidence": 0.284, "method": "correlation"}
    ]
  }
}
```

---

**Generate Narrative** *(calls Claude claude-sonnet-4-6 — returns executive summary + recommendations)*
```
meta {
  name: Generate Narrative
  type: http
  seq: 7
}

post {
  url: {{baseUrl}}/narrate
  body: json
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

body:json {
  {
    "prescription_id": "replace-with-prescription-id",
    "trace_id": "demo-001",
    "rca_summary": "Top root cause: 'temperature' with confidence 0.95. Identified 2 contributing factors.",
    "root_causes": [
      {"feature": "temperature", "effect_size": 17.241, "confidence": 0.945, "method": "correlation"},
      {"feature": "pressure",    "effect_size":  5.632, "confidence": 0.849, "method": "correlation"}
    ],
    "actions": [
      {
        "description": "Inspect heating/cooling elements and PID controller tuning",
        "target_feature": "temperature",
        "adjustment": "decrease",
        "expected_impact": 0.945,
        "priority": 1
      },
      {
        "description": "Check pressure regulator and upstream supply lines for blockage or leak",
        "target_feature": "pressure",
        "adjustment": "increase",
        "expected_impact": 0.849,
        "priority": 2
      }
    ]
  }
}
```

---

**Audit Log** *(filter by trace_id, service, from/to datetime, or limit)*
```
meta {
  name: Audit Log
  type: http
  seq: 8
}

get {
  url: {{baseUrl}}/audit?trace_id=demo-001&limit=50
  body: none
  auth: bearer
}

auth:bearer {
  token: {{token}}
}

params:query {
  trace_id: demo-001
  limit: 50
}
```

### Run experiments locally (no Docker needed)

```bash
pip install -r requirements.txt
python experiments/run_experiments.py
# Results written to experiments/outputs/
```

---

## Experiment Results

Validated on 200 rows of simulated manufacturing sensor data. A fault was injected at rows 45–55: temperature spiked +20 °C, pressure dropped –30 bar, and output quality fell 25 units.

### Anomaly Detection

| Detector | Anomalies flagged | Precision on fault rows |
|---|---|---|
| Z-Score (3σ threshold) | 11 | 100% |
| Isolation Forest (5% contamination) | 10 | 100% |
| LSTM Autoencoder | 8 | 62% |

Z-Score and Isolation Forest achieved perfect precision with zero false positives. The LSTM detected the fault peak but lagged on onset by ~6 rows and generated 3 false positives past the window edge.

### Root Cause Analysis

| Feature | Effect size | Confidence | Method |
|---|---|---|---|
| Temperature | 17.241 | 0.945 | correlation |
| Pressure | 5.632 | 0.849 | correlation |
| Vibration | 0.396 | 0.284 | correlation |
| Flow rate | 0.033 | 0.032 | correlation |

Temperature and pressure are the genuine fault drivers. The Granger test found no significant lagged predictors (p > 0.05 for all pairs), confirming this was a sudden spike rather than a slowly building trend.

### Prescriptive Actions (60% resource budget)

The LP optimiser selected the two highest-impact interventions:
1. **Temperature** — inspect cooling elements, PID tuning, thermocouple calibration
2. **Pressure** — check pressure regulator, upstream lines, set a ±10 bar real-time alert

---

## Configuration

Copy `.env.example` to `.env` and set the following:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Required — Anthropic API key for the narrative service |
| `JWT_SECRET` | Secret for signing auth tokens (change before deploying) |
| `DATABASE_URL` | Postgres connection string |
| `REDIS_URL` | Redis connection string |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker address |

Service URLs (`INGESTION_URL`, `ANOMALY_URL`, etc.) default to the Docker Compose service names and only need overriding when running services outside Docker.
