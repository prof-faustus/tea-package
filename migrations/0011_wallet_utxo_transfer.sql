-- 0011_wallet_utxo_transfer — UTXO set + transfers (REQ-DATA-0082..0084).
-- locking_script is guarded against forbidden templates by the trigger installed
-- in 0027 (Layer 3 of the four-layer prohibition enforcement).
BEGIN;

CREATE TABLE wallet.utxo (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    wallet_id     BIGINT NOT NULL REFERENCES wallet.wallet(id),
    address_id    BIGINT NOT NULL REFERENCES wallet.address(id),
    txid          BYTEA NOT NULL,
    output_index  INTEGER NOT NULL,
    satoshis      BIGINT NOT NULL CHECK (satoshis >= 0),
    locking_script BYTEA NOT NULL,
    asset_kind    TEXT NOT NULL CHECK (asset_kind IN ('BSV','TOKEN')),
    token_protocol TEXT,
    token_asset_id TEXT,
    token_amount_minor BIGINT,
    state         TEXT NOT NULL DEFAULT 'UNSPENT'
                  CHECK (state IN ('UNSPENT','RESERVED','SPENT','REORGED')),
    confirmations INTEGER NOT NULL DEFAULT 0,
    block_height  BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT utxo_txid_len CHECK (octet_length(txid) = 32),
    CONSTRAINT utxo_uniq UNIQUE (txid, output_index)
);
CREATE INDEX utxo_wallet_state_idx ON wallet.utxo(wallet_id, state);
CREATE INDEX utxo_address_idx ON wallet.utxo(address_id);
CREATE INDEX utxo_token_idx ON wallet.utxo(token_protocol, token_asset_id) WHERE asset_kind='TOKEN';

CREATE TABLE wallet.transfer (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    wallet_id     BIGINT NOT NULL REFERENCES wallet.wallet(id),
    direction     TEXT NOT NULL CHECK (direction IN ('SEND','RECEIVE')),
    asset_kind    TEXT NOT NULL CHECK (asset_kind IN ('BSV','TOKEN')),
    token_protocol TEXT,
    token_asset_id TEXT,
    amount_minor  BIGINT NOT NULL CHECK (amount_minor >= 0),
    counterparty_address TEXT,
    txid          BYTEA,
    fee_satoshis  BIGINT,
    status        TEXT NOT NULL DEFAULT 'INTENT'
                  CHECK (status IN ('INTENT','BUILT','BROADCAST','UNKNOWN','CONFIRMED','REORGED','FAILED')),
    idempotency_key TEXT NOT NULL,
    driver_id     TEXT,
    approval_id   BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT transfer_idem_uniq UNIQUE (entity_id, idempotency_key),
    CONSTRAINT transfer_txid_len CHECK (txid IS NULL OR octet_length(txid) = 32)
);
CREATE INDEX transfer_status_idx ON wallet.transfer(entity_id, status);
CREATE INDEX transfer_txid_idx ON wallet.transfer(txid);

INSERT INTO core.schema_migration(version) VALUES ('0011_wallet_utxo_transfer');
COMMIT;
