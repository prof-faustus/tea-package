-- 0016_grants_revocations — the application DB role and the privilege-based
-- immutability guard (REQ-DATA-0141, REQ-BUILD-0062). The app role has SELECT/
-- INSERT/UPDATE/DELETE on operational tables but is REVOKED UPDATE/DELETE on the
-- append-only evidence tables, so even if application code (or a trigger) were
-- bypassed, the append-only invariant holds at the privilege layer too. This is a
-- second, independent mechanism alongside the immutability triggers.
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tea_app') THEN
        CREATE ROLE tea_app LOGIN PASSWORD 'tea_app' NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA core, evid, wallet, msg, authz, ops, gl TO tea_app;

-- broad operational access on the Package schemas...
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA core, wallet, msg, authz, ops TO tea_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA evid TO tea_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA core, evid, wallet, msg, authz, ops TO tea_app;
GRANT SELECT ON ALL TABLES IN SCHEMA gl TO tea_app;

-- ...but NO UPDATE/DELETE on the append-only evidence tables (REQ-DATA-0141/0068).
REVOKE UPDATE, DELETE ON evid.canonical_record FROM tea_app;
REVOKE UPDATE, DELETE ON evid.audit_chain FROM tea_app;

INSERT INTO core.schema_migration(version) VALUES ('0016_grants_revocations');
COMMIT;
