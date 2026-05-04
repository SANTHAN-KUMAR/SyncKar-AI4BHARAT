-- SyncKar PostgreSQL Schema
-- Aligned with ARCHITECTURE.md §10

-- ─── Outbox (Transactional Outbox Pattern) ───
CREATE TABLE IF NOT EXISTS outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    ubid TEXT NOT NULL,
    source_system TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    target_topic TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    broker_sequence BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON outbox(created_at);

-- ─── Audit Ledger (BSA 2023–Compliant, Append-Only) ───
-- Exact schema from ARCHITECTURE.md §10
CREATE TABLE IF NOT EXISTS audit_ledger (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    ubid TEXT NOT NULL,
    field_modified TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    source_system TEXT NOT NULL,
    target_system TEXT NOT NULL,
    api_endpoint TEXT NOT NULL,
    source_ip TEXT NOT NULL,
    conflict_detected BOOLEAN NOT NULL DEFAULT false,
    resolution_policy TEXT,
    broker_seq_a BIGINT,
    broker_seq_b BIGINT,
    temporal_confidence TEXT,
    payload_sha256 TEXT NOT NULL,
    rsa_signature TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_ledger(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_ubid ON audit_ledger(ubid);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_ledger(created_at);

-- ─── Conflict Log ───
CREATE TABLE IF NOT EXISTS conflict_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID NOT NULL,
    ubid TEXT NOT NULL,
    field TEXT NOT NULL,
    source_a JSONB NOT NULL,
    source_b JSONB NOT NULL,
    policy_applied TEXT NOT NULL,
    winning_value TEXT NOT NULL,
    losing_value TEXT NOT NULL,
    temporal_confidence TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conflict_ubid ON conflict_log(ubid);
CREATE INDEX IF NOT EXISTS idx_conflict_created_at ON conflict_log(created_at);

-- ─── Dead Letter Queue ───
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id UUID,
    ubid TEXT,
    raw_payload JSONB NOT NULL,
    error_reason TEXT NOT NULL,
    source_system TEXT,
    target_system TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_queue(status);

-- ─── Department Snapshots (for Tier 4 snapshot diff) ───
CREATE TABLE IF NOT EXISTS dept_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_id TEXT NOT NULL,
    ubid TEXT NOT NULL,
    row_hash TEXT NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(system_id, ubid)
);

-- ─── Poller State (watermarks persisted to DB) ───
CREATE TABLE IF NOT EXISTS poller_state (
    system_id TEXT PRIMARY KEY,
    watermark TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─── Enforce append-only on audit_ledger ───
-- Create a restricted application role that can only INSERT.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'synckar_app') THEN
        CREATE ROLE synckar_app LOGIN PASSWORD 'synckar_app';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO synckar_app;
GRANT SELECT, INSERT ON audit_ledger TO synckar_app;
GRANT SELECT, INSERT, UPDATE ON outbox, conflict_log, dead_letter_queue, dept_snapshots, poller_state TO synckar_app;
-- Explicitly: NO UPDATE or DELETE on audit_ledger
REVOKE UPDATE, DELETE ON audit_ledger FROM synckar_app;
