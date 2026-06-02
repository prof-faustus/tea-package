-- 0015_ops — idempotency, work queue, dead-letter, state-machine log, recon, incidents
-- (REQ-DATA-0063/0120..0123).
BEGIN;

CREATE TABLE ops.idempotency (
    key         TEXT PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    operation   TEXT NOT NULL,
    response_hash BYTEA,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ops.work_queue (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    queue       TEXT NOT NULL CHECK (queue IN ('NOTE_BUILD','ANCHOR','CONFIRM','MATCH','RECONCILE')),
    payload     JSONB NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 25,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT NOT NULL DEFAULT 'READY'
                CHECK (status IN ('READY','IN_FLIGHT','DONE','DEAD_LETTER')),
    locked_by   TEXT,
    locked_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX work_queue_ready_idx ON ops.work_queue(queue, status, next_attempt_at);

CREATE TABLE ops.dead_letter (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    queue       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    last_error  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ops.state_transition (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    subject_type TEXT NOT NULL,
    subject_id  BIGINT NOT NULL,
    from_state  TEXT,
    to_state    TEXT NOT NULL,
    reason      TEXT,
    actor       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX state_transition_subject_idx ON ops.state_transition(subject_type, subject_id);

CREATE TABLE ops.reconciliation_run (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    kind        TEXT NOT NULL CHECK (kind IN ('CHAIN','ANCHOR','WALLET','GL_EVIDENCE','SUSPENSE')),
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    result      TEXT CHECK (result IN ('CLEAN','DISCREPANCY','ERROR')),
    detail      JSONB
);

CREATE TABLE ops.incident (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    severity    TEXT NOT NULL CHECK (severity IN ('INFO','WARN','CRITICAL','BLOCKER')),
    kind        TEXT NOT NULL,
    detail      JSONB NOT NULL,
    resolved    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

INSERT INTO core.schema_migration(version) VALUES ('0015_ops');
COMMIT;
