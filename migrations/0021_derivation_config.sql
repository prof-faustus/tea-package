-- 0021_derivation_config — install-selected deterministic salt rule + history (REQ-DATA-0171/0171A).
-- salt_rule is constrained to the two DETERMINISTIC rules; a random salt is unrepresentable.
BEGIN;

CREATE TABLE core.derivation_config (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id       BIGINT NOT NULL REFERENCES core.entity(id),
    salt_rule       TEXT NOT NULL DEFAULT 'CONTEXT'
                    CHECK (salt_rule IN ('CONTEXT','SHARED_SECRET')),
    effective_from_seq BIGINT NOT NULL,
    set_by          BIGINT REFERENCES core.app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT derivation_config_seq_uniq UNIQUE (entity_id, effective_from_seq)
);
CREATE INDEX derivation_config_entity_idx ON core.derivation_config(entity_id, effective_from_seq);

INSERT INTO core.schema_migration(version) VALUES ('0021_derivation_config');
COMMIT;
