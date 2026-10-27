#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_FILE="$PROJECT_ROOT/.pids"
LOG_DIR="$PROJECT_ROOT/.logs"

# Activate virtual environment if present
if [[ -f "$PROJECT_ROOT/.venv/bin/activate" ]]; then
  source "$PROJECT_ROOT/.venv/bin/activate"
else
  echo "ERROR: .venv not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

export RCA_PROJECT_ROOT="$PROJECT_ROOT"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
export DATABASE_URL="${DATABASE_URL:-postgresql://rca_user:rca_pass@localhost:5432/rca_platform}"
export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
export JWT_SECRET="${JWT_SECRET:-supersecretkey}"
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:?Error: ANTHROPIC_API_KEY is not set. Export it or add to .env}"

export INGESTION_URL="http://localhost:8001"
export ANOMALY_URL="http://localhost:8002"
export RCA_URL="http://localhost:8003"
export PRESCRIPTIVE_URL="http://localhost:8004"
export NARRATIVE_URL="http://localhost:8005"
export GOVERNANCE_URL="http://localhost:8006"

# Load .env if present
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -o allexport
  source "$PROJECT_ROOT/.env"
  set +o allexport
fi

mkdir -p "$LOG_DIR"
> "$PIDS_FILE"

check_dep() {
  local name="$1" cmd="$2"
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $name not found. Install with: $3"
    exit 1
  fi
}

check_dep python3 python3 "brew install python"
check_dep uvicorn uvicorn "pip install uvicorn"

echo "Checking Redis..."
if ! redis-cli ping &>/dev/null; then
  echo "ERROR: Redis not running. Start with: brew services start redis"
  exit 1
fi

echo "Checking PostgreSQL..."
if ! pg_isready -h localhost -U rca_user -d rca_platform &>/dev/null; then
  echo "WARNING: PostgreSQL not reachable at localhost:5432 with rca_user/rca_platform"
  echo "  Start postgres: brew services start postgresql@15"
  echo "  Create DB:      psql postgres -c \"CREATE USER rca_user WITH PASSWORD 'rca_pass';\""
  echo "                  psql postgres -c \"CREATE DATABASE rca_platform OWNER rca_user;\""
  echo "  Run schema:     psql -U rca_user rca_platform < infra/postgres/init.sql"
  echo "Continuing anyway (ingestion/governance may fail)..."
fi

start_service() {
  local name="$1" port="$2" dir="$3"
  echo "Starting $name on :$port ..."
  PYTHONPATH="$PROJECT_ROOT" uvicorn main:app \
    --host 0.0.0.0 \
    --port "$port" \
    --app-dir "$PROJECT_ROOT/services/$dir" \
    --log-level info \
    > "$LOG_DIR/$name.log" 2>&1 &
  echo "$!" >> "$PIDS_FILE"
  echo "  PID $! — logs: .logs/$name.log"
}

start_service governance  8006 governance
start_service ingestion   8001 ingestion
start_service anomaly     8002 anomaly
start_service rca         8003 rca
start_service prescriptive 8004 prescriptive
start_service narrative   8005 narrative
start_service gateway     8000 gateway

echo ""
echo "All services started. API Gateway: http://localhost:8000"
echo "API docs:  http://localhost:8000/docs"
echo "Health:    http://localhost:8000/health"
echo ""
echo "Stop with: ./stop.sh"
