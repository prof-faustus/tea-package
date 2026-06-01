-- 0008_evid_notes — engine note projection + the lineage spine (REQ-DATA-0070..0072).
-- evid.note stores engine outputs verbatim (populated from Stage 3 onward);
-- evid.lineage is the spine joining GL txn <-> canonical record <-> chain <-> note <-> anchor.
BEGIN;

CREATE TABLE evid.note (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    canonical_id  BIGINT NOT NULL REFERENCES evid.canonical_record(id),
    note_type     TEXT NOT NULL CHECK (note_type IN ('INVOICE_NOTE','PAYMENT_NOTE')),
    note_id_bytes BYTEA NOT NULL,
    note_body     BYTEA NOT NULL,
    l_tag         BYTEA NOT NULL,
    linked_note_id BIGINT REFERENCES evid.note(id),
    key_path      TEXT NOT NULL,
    counterparty_pubkey BYTEA NOT NULL,
    signature     BYTEA NOT NULL,
    status        TEXT NOT NULL DEFAULT 'NOTE_BUILT'
                  CHECK (status IN ('NOTE_BUILT','ANCHOR_PENDING','ANCHORED','CONFIRMED','REORGED','FAILED')),
    engine_version TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT cp_pubkey_len CHECK (octet_length(counterparty_pubkey) = 33)
);
CREATE INDEX note_entity_type_idx ON evid.note(entity_id, note_type);
CREATE INDEX note_canonical_idx ON evid.note(canonical_id);
CREATE INDEX note_linked_idx ON evid.note(linked_note_id);
CREATE UNIQUE INDEX note_idbytes_uniq ON evid.note(entity_id, note_id_bytes);

CREATE TABLE evid.lineage (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    correlation_id UUID NOT NULL,
    gl_txn_id     BIGINT,
    canonical_id  BIGINT NOT NULL REFERENCES evid.canonical_record(id),
    audit_seq     BIGINT,
    note_id       BIGINT REFERENCES evid.note(id),
    wallet_transfer_id BIGINT,
    state         TEXT NOT NULL DEFAULT 'POSTED'
                  CHECK (state IN ('DRAFT','POSTED','NOTE_BUILT','ANCHOR_PENDING',
                                   'ANCHORED','CONFIRMED','NOTE_BUILD_FAILED','ANCHOR_FAILED','REORGED')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT lineage_corr_idx UNIQUE (entity_id, correlation_id, canonical_id)
);
CREATE INDEX lineage_state_idx ON evid.lineage(entity_id, state);
CREATE INDEX lineage_gltxn_idx ON evid.lineage(gl_txn_id);
CREATE INDEX lineage_corr_lookup_idx ON evid.lineage(correlation_id);

INSERT INTO core.schema_migration(version) VALUES ('0008_evid_notes');
COMMIT;
