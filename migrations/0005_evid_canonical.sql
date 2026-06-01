-- 0005_evid_canonical — the single canonical-bytes store + integrity triggers.
-- REQ-DATA-0030 (sha recompute), REQ-DATA-0031 (immutable, no UPDATE/DELETE).
BEGIN;

CREATE TABLE evid.canonical_record (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    record_type   TEXT NOT NULL CHECK (record_type IN
                  ('INVOICE','PAYMENT','CREDIT_NOTE','ADJUSTMENT','STATEMENT','MESSAGE','WALLET_TRANSFER')),
    logical_key   TEXT NOT NULL,
    canonical_bytes  BYTEA NOT NULL,
    canonical_sha256 BYTEA NOT NULL,
    schema_version   INTEGER NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT canonical_sha_len CHECK (octet_length(canonical_sha256) = 32),
    CONSTRAINT canonical_key_uniq UNIQUE (entity_id, record_type, logical_key, canonical_sha256)
);
CREATE INDEX canonical_entity_type_idx ON evid.canonical_record(entity_id, record_type);
CREATE INDEX canonical_sha_idx ON evid.canonical_record(canonical_sha256);

-- REQ-DATA-0040: recompute SHA-256(canonical_bytes) and reject a mismatch.
CREATE OR REPLACE FUNCTION evid.fn_canonical_check() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    IF digest(NEW.canonical_bytes, 'sha256') <> NEW.canonical_sha256 THEN
        RAISE EXCEPTION 'canonical_sha256 does not match SHA-256(canonical_bytes) (REQ-DATA-0030)';
    END IF;
    RETURN NEW;
END;
$$;

-- REQ-DATA-0041: append-only — reject UPDATE/DELETE unconditionally.
CREATE OR REPLACE FUNCTION evid.fn_canonical_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RAISE EXCEPTION 'evid.canonical_record is append-only; % rejected (REQ-DATA-0031)', TG_OP;
END;
$$;

CREATE TRIGGER trg_canonical_check
    BEFORE INSERT ON evid.canonical_record
    FOR EACH ROW EXECUTE FUNCTION evid.fn_canonical_check();
CREATE TRIGGER trg_canonical_immutable
    BEFORE UPDATE OR DELETE ON evid.canonical_record
    FOR EACH ROW EXECUTE FUNCTION evid.fn_canonical_immutable();

INSERT INTO core.schema_migration(version) VALUES ('0005_evid_canonical');
COMMIT;
