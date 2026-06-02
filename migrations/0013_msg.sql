-- 0013_msg — broadcast-encrypted messaging (REQ-DATA-0100/0101). Plaintext is
-- never stored; only BIE1/ECIES ciphertext (the engine's cipher).
BEGIN;

CREATE TABLE msg.thread (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    subject     TEXT,
    created_by  BIGINT NOT NULL REFERENCES core.app_user(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX thread_entity_idx ON msg.thread(entity_id);

CREATE TABLE msg.participant (
    thread_id   BIGINT NOT NULL REFERENCES msg.thread(id),
    pubkey      BYTEA NOT NULL,
    user_id     BIGINT REFERENCES core.app_user(id),
    role        TEXT NOT NULL CHECK (role IN ('SENDER','RECIPIENT')),
    PRIMARY KEY (thread_id, pubkey),
    CONSTRAINT participant_pk_len CHECK (octet_length(pubkey) = 33)
);

CREATE TABLE msg.message (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    thread_id     BIGINT NOT NULL REFERENCES msg.thread(id),
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    sender_pubkey BYTEA NOT NULL,
    ciphertext    BYTEA NOT NULL,
    canonical_id  BIGINT REFERENCES evid.canonical_record(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT msg_sender_len CHECK (octet_length(sender_pubkey) = 33)
);
CREATE INDEX message_thread_idx ON msg.message(thread_id, created_at);

INSERT INTO core.schema_migration(version) VALUES ('0013_msg');
COMMIT;
