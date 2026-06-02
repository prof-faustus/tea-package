-- 0024_msg_message_key — one-time message keys bound to the master key + chain
-- (REQ-DATA-0174..0176). domain=4 (MESSAGE_KEY); references a chained KEY_DERIVATION
-- record; the private side is never stored (custody only).
BEGIN;

CREATE TABLE msg.message_key (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id       BIGINT NOT NULL REFERENCES core.entity(id),
    thread_id       BIGINT NOT NULL REFERENCES msg.thread(id),
    counterparty_id BIGINT NOT NULL REFERENCES core.counterparty(id),
    wallet_id       BIGINT NOT NULL REFERENCES wallet.wallet(id),
    scheme_version  INTEGER NOT NULL,
    derivation_domain SMALLINT NOT NULL DEFAULT 4 CHECK (derivation_domain = 4),
    invoice_number  BIGINT NOT NULL DEFAULT 0,
    payment_index   BIGINT NOT NULL,
    derived_pubkey  BYTEA NOT NULL,
    salt_det        BYTEA NOT NULL,
    salt_commitment BYTEA NOT NULL,
    key_derivation_canonical_id BIGINT NOT NULL REFERENCES evid.canonical_record(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT msgkey_pub_len CHECK (octet_length(derived_pubkey) = 33),
    CONSTRAINT msgkey_salt_len CHECK (octet_length(salt_det) = 32 AND octet_length(salt_commitment) = 32),
    CONSTRAINT msgkey_ctx_uniq UNIQUE (entity_id, counterparty_id, thread_id, scheme_version, invoice_number, payment_index)
);
CREATE INDEX msgkey_thread_idx ON msg.message_key(thread_id);

INSERT INTO core.schema_migration(version) VALUES ('0024_msg_message_key');
COMMIT;
