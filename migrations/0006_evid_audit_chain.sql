-- 0006_evid_audit_chain — the append-only per-entity hash chain + verifier.
-- REQ-DATA-0032..0036, 0042, 0043, 0045.
BEGIN;

CREATE TABLE evid.audit_chain (
    seq           BIGINT NOT NULL,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    canonical_id  BIGINT NOT NULL REFERENCES evid.canonical_record(id),
    prev_hash     BYTEA NOT NULL,
    entry_hash    BYTEA NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, seq),
    CONSTRAINT prev_hash_len CHECK (octet_length(prev_hash) = 32),
    CONSTRAINT entry_hash_len CHECK (octet_length(entry_hash) = 32)
);
CREATE INDEX audit_canonical_idx ON evid.audit_chain(canonical_id);

-- REQ-DATA-0042: single-writer, gap-free, prev/entry recomputed and asserted.
CREATE OR REPLACE FUNCTION evid.fn_audit_append() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    last_seq      BIGINT;
    expected_prev BYTEA;
    csha          BYTEA;
    crec_entity   BIGINT;
    expected_entry BYTEA;
    zero32 CONSTANT BYTEA := decode(repeat('00', 32), 'hex');
BEGIN
    -- 1. one writer per entity-chain (REQ-DATA-0036)
    PERFORM pg_advisory_xact_lock(hashtext('audit_chain'), NEW.entity_id::int);

    -- 2. gap-free seq (REQ-DATA-0032)
    SELECT COALESCE(max(seq), 0) INTO last_seq
        FROM evid.audit_chain WHERE entity_id = NEW.entity_id;
    IF NEW.seq <> last_seq + 1 THEN
        RAISE EXCEPTION 'audit_chain seq must be %, got % (REQ-DATA-0032)', last_seq + 1, NEW.seq;
    END IF;

    -- 3. prev_hash linkage (REQ-DATA-0034)
    IF last_seq = 0 THEN
        expected_prev := zero32;
    ELSE
        SELECT entry_hash INTO expected_prev
            FROM evid.audit_chain WHERE entity_id = NEW.entity_id AND seq = last_seq;
    END IF;
    IF NEW.prev_hash <> expected_prev THEN
        RAISE EXCEPTION 'audit_chain prev_hash mismatch at seq % (REQ-DATA-0034)', NEW.seq;
    END IF;

    -- 4. entry_hash = SHA-256(prev_hash || canonical_sha256) (REQ-DATA-0033)
    SELECT canonical_sha256, entity_id INTO csha, crec_entity
        FROM evid.canonical_record WHERE id = NEW.canonical_id;
    IF csha IS NULL THEN
        RAISE EXCEPTION 'audit_chain references missing canonical_record %', NEW.canonical_id;
    END IF;
    IF crec_entity <> NEW.entity_id THEN
        RAISE EXCEPTION 'audit_chain entity % does not match canonical_record entity % (REQ-DATA-0010)',
            NEW.entity_id, crec_entity;
    END IF;
    expected_entry := digest(NEW.prev_hash || csha, 'sha256');
    IF NEW.entry_hash <> expected_entry THEN
        RAISE EXCEPTION 'audit_chain entry_hash mismatch at seq % (REQ-DATA-0033)', NEW.seq;
    END IF;

    RETURN NEW;
END;
$$;

-- REQ-DATA-0043: append-only — reject UPDATE/DELETE unconditionally.
CREATE OR REPLACE FUNCTION evid.fn_audit_immutable() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    RAISE EXCEPTION 'evid.audit_chain is append-only; % rejected (REQ-DATA-0035)', TG_OP;
END;
$$;

-- REQ-DATA-0045: walk the chain, return the first broken seq or NULL if intact.
CREATE OR REPLACE FUNCTION evid.fn_verify_chain(p_entity_id BIGINT) RETURNS BIGINT
LANGUAGE plpgsql STABLE AS $$
DECLARE
    r RECORD;
    prev BYTEA := decode(repeat('00', 32), 'hex');
    expected_entry BYTEA;
    expected_seq BIGINT := 1;
BEGIN
    FOR r IN
        SELECT ac.seq, ac.prev_hash, ac.entry_hash, cr.canonical_sha256
        FROM evid.audit_chain ac
        JOIN evid.canonical_record cr ON cr.id = ac.canonical_id
        WHERE ac.entity_id = p_entity_id
        ORDER BY ac.seq
    LOOP
        IF r.seq <> expected_seq THEN RETURN expected_seq; END IF;        -- gap
        IF r.prev_hash <> prev THEN RETURN r.seq; END IF;                 -- broken linkage
        expected_entry := digest(r.prev_hash || r.canonical_sha256, 'sha256');
        IF r.entry_hash <> expected_entry THEN RETURN r.seq; END IF;      -- tampered
        prev := r.entry_hash;
        expected_seq := expected_seq + 1;
    END LOOP;
    RETURN NULL;   -- intact
END;
$$;

CREATE TRIGGER trg_audit_append
    BEFORE INSERT ON evid.audit_chain
    FOR EACH ROW EXECUTE FUNCTION evid.fn_audit_append();
CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON evid.audit_chain
    FOR EACH ROW EXECUTE FUNCTION evid.fn_audit_immutable();

INSERT INTO core.schema_migration(version) VALUES ('0006_evid_audit_chain');
COMMIT;
