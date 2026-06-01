-- 0007_evid_chain_anchor — periodic anchoring of the chain head (REQ-DATA-0037).
BEGIN;

CREATE TABLE evid.chain_anchor (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    head_seq    BIGINT NOT NULL,
    head_hash   BYTEA NOT NULL,
    anchor_txid BYTEA,
    anchor_status TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (anchor_status IN ('PENDING','BROADCAST','CONFIRMED','REORGED','FAILED')),
    merkle_proof_ref BIGINT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    CONSTRAINT head_hash_len CHECK (octet_length(head_hash) = 32),
    CONSTRAINT anchor_txid_len CHECK (anchor_txid IS NULL OR octet_length(anchor_txid) = 32),
    CONSTRAINT chain_anchor_head_uniq UNIQUE (entity_id, head_seq)
);
CREATE INDEX chain_anchor_entity_idx ON evid.chain_anchor(entity_id);
CREATE INDEX chain_anchor_status_idx ON evid.chain_anchor(anchor_status);

INSERT INTO core.schema_migration(version) VALUES ('0007_evid_chain_anchor');
COMMIT;
