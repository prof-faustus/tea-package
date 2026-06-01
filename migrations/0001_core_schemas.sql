-- 0001_core_schemas — CREATE the namespaces + the migration ledger + pgcrypto.
-- Reversibility: schemas are dropped in the downgrade (operational, not chained).
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;       -- digest() for canonical/chain hashing

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS evid;
CREATE SCHEMA IF NOT EXISTS wallet;
CREATE SCHEMA IF NOT EXISTS msg;
CREATE SCHEMA IF NOT EXISTS authz;
CREATE SCHEMA IF NOT EXISTS ops;

-- Applied-migration ledger (REQ-DATA-0130: ordered, immutable, forward).
CREATE TABLE IF NOT EXISTS core.schema_migration (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO core.schema_migration(version) VALUES ('0001_core_schemas')
    ON CONFLICT DO NOTHING;

COMMIT;
