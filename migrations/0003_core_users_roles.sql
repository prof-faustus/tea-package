-- 0003_core_users_roles — users, roles, entity-scoped grants (REQ-DATA-0014/0015).
BEGIN;

CREATE TABLE core.app_user (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    display_name  TEXT,
    status        TEXT NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE','DISABLED','LOCKED')),
    auth_ref      TEXT NOT NULL,
    mfa_enrolled  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.role (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE core.user_role (
    user_id   BIGINT NOT NULL REFERENCES core.app_user(id),
    role_id   BIGINT NOT NULL REFERENCES core.role(id),
    entity_id BIGINT NOT NULL REFERENCES core.entity(id),
    granted_by BIGINT REFERENCES core.app_user(id),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id, entity_id)
);
CREATE INDEX user_role_role_idx ON core.user_role(role_id);
CREATE INDEX user_role_entity_idx ON core.user_role(entity_id);

INSERT INTO core.schema_migration(version) VALUES ('0003_core_users_roles');
COMMIT;
