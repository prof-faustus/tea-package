-- 0019_counterparty — counterparty master public keys + verification state (REQ-DATA-0160/0162).
BEGIN;

CREATE TABLE core.counterparty (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id       BIGINT NOT NULL REFERENCES core.entity(id),
    display_name    TEXT NOT NULL,
    counterparty_uid BYTEA NOT NULL,
    master_pubkey   BYTEA,
    master_pubkey_status TEXT NOT NULL DEFAULT 'UNVERIFIED'
                    CHECK (master_pubkey_status IN ('UNVERIFIED','VERIFIED','REVOKED')),
    master_pubkey_provenance TEXT,
    master_pubkey_verified_by BIGINT REFERENCES core.app_user(id),
    master_pubkey_verified_at TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','SUSPENDED','CLOSED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cp_uid_uniq UNIQUE (entity_id, counterparty_uid),
    CONSTRAINT cp_uid_len CHECK (octet_length(counterparty_uid) = 16),
    CONSTRAINT cp_master_len CHECK (master_pubkey IS NULL OR octet_length(master_pubkey) = 33)
);
CREATE INDEX cp_entity_idx ON core.counterparty(entity_id);
CREATE UNIQUE INDEX cp_master_uniq ON core.counterparty(entity_id, master_pubkey)
    WHERE master_pubkey IS NOT NULL;

INSERT INTO core.schema_migration(version) VALUES ('0019_counterparty');
COMMIT;
