-- 0004_gl_bootstrap — create the gl namespace and record the GL library version.
-- The python-accounting tables are created by the library's own create_all
-- (REQ-DATA-0020) in the Stage-2 bootstrap step, which UPDATES the version row
-- below from 'PENDING' to the exact applied version (REQ-DATA-0140). This
-- migration owns only the namespace and the version-recording contract.
BEGIN;

CREATE SCHEMA IF NOT EXISTS gl;

INSERT INTO core.component_version(component, version, notes)
VALUES ('python-accounting', 'PENDING', 'create_all + exact version recorded in Stage-2 bootstrap (REQ-DATA-0020/0140)')
ON CONFLICT (component) DO NOTHING;

INSERT INTO core.schema_migration(version) VALUES ('0004_gl_bootstrap');
COMMIT;
