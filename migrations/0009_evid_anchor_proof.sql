-- 0009_evid_anchor_proof — Layer-A anchoring (Merkle) + Layer-B selective shards.
-- REQ-DATA-0073..0076. No data-carrier or script-hash outputs anywhere; the anchor
-- tx uses an allowed spendable template (enforced at the wallet layer + the gates).
BEGIN;

CREATE TABLE evid.anchor_batch (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    merkle_root   BYTEA NOT NULL,
    anchor_txid   BYTEA,
    output_index  INTEGER,
    status        TEXT NOT NULL DEFAULT 'PENDING'
                  CHECK (status IN ('PENDING','BROADCAST','CONFIRMED','REORGED','FAILED')),
    network       TEXT NOT NULL CHECK (network IN ('REGTEST','TESTNET','MAINNET')),
    broadcast_at  TIMESTAMPTZ,
    confirmed_at  TIMESTAMPTZ,
    block_hash    BYTEA,
    block_height  BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT merkle_root_len CHECK (octet_length(merkle_root) = 32),
    CONSTRAINT anchor_batch_txid_len CHECK (anchor_txid IS NULL OR octet_length(anchor_txid) = 32),
    CONSTRAINT anchor_batch_block_hash_len CHECK (block_hash IS NULL OR octet_length(block_hash) = 32)
);
CREATE INDEX anchor_batch_entity_idx ON evid.anchor_batch(entity_id);
CREATE INDEX anchor_batch_status_idx ON evid.anchor_batch(status);

CREATE TABLE evid.anchor_member (
    batch_id   BIGINT NOT NULL REFERENCES evid.anchor_batch(id),
    note_id    BIGINT NOT NULL REFERENCES evid.note(id),
    leaf_index INTEGER NOT NULL,
    leaf_hash  BYTEA NOT NULL,
    PRIMARY KEY (batch_id, note_id),
    CONSTRAINT leaf_hash_len CHECK (octet_length(leaf_hash) = 32),
    CONSTRAINT leaf_index_uniq UNIQUE (batch_id, leaf_index)
);

CREATE TABLE evid.merkle_proof (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    batch_id      BIGINT NOT NULL REFERENCES evid.anchor_batch(id),
    txid          BYTEA NOT NULL,
    proof_bytes   BYTEA NOT NULL,
    block_hash    BYTEA NOT NULL,
    block_height  BIGINT NOT NULL,
    validated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT mp_txid_len CHECK (octet_length(txid) = 32),
    CONSTRAINT mp_block_hash_len CHECK (octet_length(block_hash) = 32)
);
CREATE INDEX merkle_proof_batch_idx ON evid.merkle_proof(batch_id);

CREATE TABLE evid.proof_shard (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    proof_id      BIGINT NOT NULL REFERENCES evid.merkle_proof(id),
    shard_key     TEXT NOT NULL,
    shard_attribute TEXT NOT NULL CHECK (shard_attribute IN
                  ('TXID','INOUT_FLAG','INOUT_POSITION','LOCKING_SCRIPT',
                   'UNLOCKING_SCRIPT','AMOUNT_MINOR','POSITION_IN_BLOCK')),
    shard_bytes   BYTEA NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT shard_uniq UNIQUE (proof_id, shard_attribute)
);
CREATE INDEX shard_key_idx ON evid.proof_shard(shard_key);

INSERT INTO core.schema_migration(version) VALUES ('0009_evid_anchor_proof');
COMMIT;
