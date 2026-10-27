-- Ingested data store
CREATE TABLE IF NOT EXISTS ingested_datasets (
    trace_id        TEXT PRIMARY KEY,
    source_type     TEXT NOT NULL,
    columns         JSONB NOT NULL,
    rows            JSONB NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit log (governance service writes here)
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id        TEXT PRIMARY KEY,
    trace_id        TEXT NOT NULL,
    service         TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_trace   ON audit_log(trace_id);
CREATE INDEX IF NOT EXISTS idx_audit_service ON audit_log(service);
CREATE INDEX IF NOT EXISTS idx_audit_time    ON audit_log(timestamp);
