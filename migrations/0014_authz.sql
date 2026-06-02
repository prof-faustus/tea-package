-- 0014_authz — permissions, spend policy, approvals (REQ-DATA-0110/0111).
BEGIN;

CREATE TABLE authz.permission (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE
);

CREATE TABLE authz.role_permission (
    role_id       BIGINT NOT NULL REFERENCES core.role(id),
    permission_id BIGINT NOT NULL REFERENCES authz.permission(id),
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE authz.spend_policy (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    wallet_id     BIGINT REFERENCES wallet.wallet(id),
    asset_kind    TEXT NOT NULL CHECK (asset_kind IN ('BSV','TOKEN','ANY')),
    per_txn_limit_minor BIGINT,
    daily_limit_minor   BIGINT,
    requires_approval_above_minor BIGINT,
    approver_count SMALLINT NOT NULL DEFAULT 1,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE authz.approval (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    subject_type  TEXT NOT NULL CHECK (subject_type IN ('WALLET_SEND','WALLET_MINT','WALLET_BURN','DISCLOSURE')),
    subject_ref   BIGINT NOT NULL,
    requested_by  BIGINT NOT NULL REFERENCES core.app_user(id),
    approved_by   BIGINT[] NOT NULL DEFAULT '{}',
    required_count SMALLINT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX approval_status_idx ON authz.approval(entity_id, status);

INSERT INTO core.schema_migration(version) VALUES ('0014_authz');
COMMIT;
