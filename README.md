# RCA Platform

An end-to-end, event-driven microservices platform that automatically detects anomalies in operational data, identifies their root causes using causal inference, prescribes prioritised remediation actions, and delivers the findings as plain-English business narratives via Claude AI.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Services](#services)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Experiment Results](#experiment-results)
- [Configuration](#configuration)
- [Project Structure](#project-structure)

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

```
  ┌───────────────────────────────────────────────────────────────┐
  │                      External Sources                         │
  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
  │  │  Oracle APEX │    │  Salesforce  │    │   SAP BTP    │    │
  └──┴──────┬───────┴────┴──────┬───────┴────┴──────┬───────┴────┘
             └──────────────────┼──────────────────┘
                                │  REST / Kafka / PostgreSQL
                                ▼
                    ┌───────────────────────┐
                    │    Gateway Service    │  :8000
                    │  JWT auth · routing   │
                    └───────────┬───────────┘
                                │
              ┌─────────────────▼─────────────────┐
              │         Ingestion Service          │  :8001  ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┐
              └─────────────────┬─────────────────┘                           ╎
                          data.ingested                                        ╎
                  ┌─────────────▼──────────────────┐                          ╎
                  │       Anomaly Service           │  :8002  ╌╌╌╌╌╌╌╌╌╌╌╌╌┐ ╎
                  └─────────────┬──────────────────┘                       ╎ ╎
                          anomaly.detected                                  ╎ ╎
                       ┌────────▼───────────────────┐                      ╎ ╎
                       │        RCA Service          │  :8003  ╌╌╌╌╌╌╌╌╌┐  ╎ ╎
                       └────────┬───────────────────┘                   ╎  ╎ ╎
                          rca.complete                                   ╎  ╎ ╎
                          ┌─────▼──────────────────────┐                ╎  ╎ ╎
                          │    Prescriptive Service     │  :8004  ╌╌╌╌┐ ╎  ╎ ╎
                          └─────┬──────────────────────┘             ╎ ╎  ╎ ╎
                          prescription.ready                          ╎ ╎  ╎ ╎
                               ┌─▼────────────────────────┐          ╎ ╎  ╎ ╎
                               │    Narrative Service      │  :8005  ╌┐╎ ╎  ╎ ╎
                               │    (Claude claude-sonnet-4-6)        ││╎ ╎  ╎ ╎
                               └──────────────────────────┘          │╎ ╎  ╎ ╎
                                                                      ▼▼ ▼  ▼ ▼
                    ┌──────────────────────────────────────────────────────────┐
                    │              Governance Service  :8006                   │
                    │           PostgreSQL audit log (every event)             │
                    └──────────────────────────────────────────────────────────┘
```

Solid arrows show the main pipeline flow via Redis pub/sub events.
Dashed lines (╌╌╌) show each service also publishing every event to the Governance Service for a full audit trail.

**Event flow:**

| Event | Published by | Consumed by |
|---|---|---|
| `data_ingested` | Ingestion | Anomaly |
| `anomaly_detected` | Anomaly | RCA |
| `rca_complete` | RCA | Prescriptive |
| `prescription_ready` | Prescriptive | Narrative |
| `narrative_generated` | Narrative | — |

Every event is also consumed by the Governance service for audit logging.

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

### 3. Verify

```bash
curl http://localhost:8000/health
```

You should see `"status": "ok"` with per-service statuses.

### 4. Get an auth token

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

### 5. Run the full pipeline

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer <your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "rest",
    "connection": {"url": "https://your-data-endpoint.example.com/metrics"},
    "trace_id": "demo-001"
  }'
```

The pipeline runs asynchronously. Poll `/audit?trace_id=demo-001` to follow progress.

### Run experiments locally (no Docker needed)

```bash
pip install -r requirements.txt
python experiments/run_experiments.py
# Results written to experiments/outputs/
```

---

## API Reference

All endpoints (except `/health` and `/auth/token`) require a `Bearer` token.

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/token` | Exchange credentials for a JWT |
| `POST` | `/analyze` | Trigger the full pipeline (async) |
| `POST` | `/detect` | Run anomaly detection directly |
| `POST` | `/rca` | Run root cause analysis directly |
| `POST` | `/prescribe` | Run prescriptive optimisation directly |
| `POST` | `/narrate` | Generate a narrative directly |
| `GET` | `/audit` | Query the audit log |
| `GET` | `/health` | Aggregate health of all services |

### Trace IDs

Every request carries a `trace_id` (auto-generated UUID if not supplied). The same ID threads through every stage of the pipeline, letting you reconstruct the full decision trail from ingestion to narrative via the audit endpoint.

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

---

## Project Structure

```
rca-platform/
├── services/
│   ├── gateway/          # API gateway (JWT auth, routing)
│   ├── ingestion/        # Data ingestion (Postgres, REST, Kafka)
│   ├── anomaly/          # Anomaly detection (Z-Score, IF, LSTM)
│   │   └── detectors/
│   ├── rca/              # Root cause analysis (causal graph, DoWhy, Granger)
│   │   └── engines/
│   ├── prescriptive/     # Action optimisation (LP / knapsack)
│   │   └── optimizers/
│   ├── narrative/        # AI narrative generation (Claude)
│   └── governance/       # Audit logging (Postgres)
├── shared/               # Shared schemas, events, Redis bus
├── infra/
│   └── postgres/         # Database init SQL
├── experiments/          # Standalone experiment runner + outputs
├── docker-compose.yml
├── start.sh / stop.sh
└── .env.example
```

---

## Stopping the platform

```bash
./stop.sh
# or: docker compose down
```

To also remove stored data:

```bash
docker compose down -v
```
