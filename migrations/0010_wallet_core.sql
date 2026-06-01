-- 0010_wallet_core — native HD wallet + address (REQ-DATA-0080..0091).
-- Only key REFERENCES are stored, never private key material (REQ-DATA-0002).
BEGIN;

CREATE TABLE wallet.wallet (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    label       TEXT NOT NULL,
    hd_root_ref TEXT NOT NULL,
    network     TEXT NOT NULL CHECK (network IN ('REGTEST','TESTNET','MAINNET')),
    status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','FROZEN','CLOSED')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wallet_label_uniq UNIQUE (entity_id, label)
);
CREATE INDEX wallet_entity_idx ON wallet.wallet(entity_id);

CREATE TABLE wallet.address (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wallet_id     BIGINT NOT NULL REFERENCES wallet.wallet(id),
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    derivation_path TEXT NOT NULL,
    pubkey        BYTEA NOT NULL,
    address_text  TEXT NOT NULL,
    purpose       TEXT NOT NULL CHECK (purpose IN ('RECEIVE','CHANGE','INVOICE','FEE','TOKEN')),
    invoice_canonical_id BIGINT REFERENCES evid.canonical_record(id),
    used          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT addr_pubkey_len CHECK (octet_length(pubkey) = 33),
    CONSTRAINT addr_text_uniq UNIQUE (entity_id, address_text)
);
CREATE INDEX address_wallet_idx ON wallet.address(wallet_id);
CREATE INDEX address_entity_idx ON wallet.address(entity_id);

INSERT INTO core.schema_migration(version) VALUES ('0010_wallet_core');
COMMIT;
