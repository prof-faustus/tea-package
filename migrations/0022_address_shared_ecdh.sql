-- 0022_address_shared_ecdh — shared-ECDH derivation columns on wallet.address
-- (REQ-DATA-0163..0165). Additive columns; existing constraints stand. The
-- one-time-address guarantee is the partial UNIQUE index on the derivation tuple.
BEGIN;

ALTER TABLE wallet.address
    ADD COLUMN derivation_method TEXT NOT NULL DEFAULT 'SINGLE_PARTY_HD'
        CHECK (derivation_method IN ('SINGLE_PARTY_HD','SHARED_ECDH')),
    ADD COLUMN counterparty_id   BIGINT REFERENCES core.counterparty(id),
    ADD COLUMN scheme_version    INTEGER,
    ADD COLUMN derivation_domain SMALLINT,
    ADD COLUMN invoice_number    BIGINT,
    ADD COLUMN payment_index     BIGINT,
    ADD COLUMN key_derivation_canonical_id BIGINT REFERENCES evid.canonical_record(id),
    ADD COLUMN salt_det          BYTEA,
    ADD COLUMN salt_commitment   BYTEA,
    ADD CONSTRAINT addr_salt_det_len CHECK (salt_det IS NULL OR octet_length(salt_det) = 32),
    ADD CONSTRAINT addr_salt_commit_len CHECK (salt_commitment IS NULL OR octet_length(salt_commitment) = 32);

-- For SHARED_ECDH, the full derivation context must be present (REQ-DATA-0163).
ALTER TABLE wallet.address
    ADD CONSTRAINT addr_shared_ctx_complete CHECK (
        derivation_method <> 'SHARED_ECDH' OR (
            counterparty_id IS NOT NULL AND scheme_version IS NOT NULL AND
            derivation_domain IS NOT NULL AND invoice_number IS NOT NULL AND
            payment_index IS NOT NULL AND key_derivation_canonical_id IS NOT NULL AND
            salt_commitment IS NOT NULL
        )
    );

-- One-time-address guarantee at the storage layer (REQ-DATA-0163, REQ-WIRE-0133).
CREATE UNIQUE INDEX addr_shared_ctx_uniq ON wallet.address
    (entity_id, counterparty_id, scheme_version, derivation_domain, invoice_number, payment_index)
    WHERE derivation_method = 'SHARED_ECDH';

-- REQ-DATA-0165: a SHARED_ECDH address must reference a KEY_DERIVATION canonical
-- record of the same entity that is present in the chain. (Full cryptographic
-- field-equality between the decoded record and pubkey/address_text is enforced
-- by the application encoder building both from one engine output in a single
-- transaction, and re-verified in reconciliation, REQ-DATA-0169 — the canonical
-- bytes are deterministic CBOR not decodable in plpgsql; see DEC-0006.)
CREATE OR REPLACE FUNCTION wallet.fn_shared_address_binding() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    rt TEXT; rent BIGINT; chained BOOLEAN;
BEGIN
    IF NEW.derivation_method <> 'SHARED_ECDH' THEN
        RETURN NEW;
    END IF;
    SELECT record_type, entity_id INTO rt, rent
        FROM evid.canonical_record WHERE id = NEW.key_derivation_canonical_id;
    IF rt IS NULL THEN
        RAISE EXCEPTION 'SHARED_ECDH address references missing canonical_record %', NEW.key_derivation_canonical_id;
    END IF;
    IF rt <> 'KEY_DERIVATION' THEN
        RAISE EXCEPTION 'key_derivation_canonical_id must be a KEY_DERIVATION record, got % (REQ-DATA-0165)', rt;
    END IF;
    IF rent <> NEW.entity_id THEN
        RAISE EXCEPTION 'KEY_DERIVATION record entity % does not match address entity %', rent, NEW.entity_id;
    END IF;
    SELECT EXISTS (SELECT 1 FROM evid.audit_chain WHERE canonical_id = NEW.key_derivation_canonical_id)
        INTO chained;
    IF NOT chained THEN
        RAISE EXCEPTION 'KEY_DERIVATION record % is not chained (REQ-WIRE-0136)', NEW.key_derivation_canonical_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_shared_address_binding
    BEFORE INSERT OR UPDATE ON wallet.address
    FOR EACH ROW EXECUTE FUNCTION wallet.fn_shared_address_binding();

INSERT INTO core.schema_migration(version) VALUES ('0022_address_shared_ecdh');
COMMIT;
