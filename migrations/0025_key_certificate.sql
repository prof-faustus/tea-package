-- 0025_key_certificate — BSV outpoint-based certificate authority projection
-- (REQ-DATA-0164c..0165c, 10 §10.20-10.26) + the KEY_CERTIFICATE record type.
-- The table is a projection of the chained KEY_CERTIFICATE body; the chain is the
-- authority. Irreversible-with-data once any KEY_CERTIFICATE record exists.
BEGIN;

-- widen the canonical_record record_type set to include KEY_CERTIFICATE
ALTER TABLE evid.canonical_record
    DROP CONSTRAINT canonical_record_record_type_check,
    ADD CONSTRAINT canonical_record_record_type_check
        CHECK (record_type IN
        ('INVOICE','PAYMENT','CREDIT_NOTE','ADJUSTMENT','STATEMENT',
         'MESSAGE','WALLET_TRANSFER','KEY_DERIVATION','KEY_CERTIFICATE'));

CREATE TABLE core.key_certificate (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id               BIGINT NOT NULL REFERENCES core.entity(id),
    subject_kind            TEXT NOT NULL CHECK (subject_kind IN ('ENTITY','COUNTERPARTY')),
    counterparty_id         BIGINT REFERENCES core.counterparty(id),
    subject_master_pubkey   BYTEA NOT NULL CHECK (octet_length(subject_master_pubkey) = 33),
    revocation_rights_mode  TEXT NOT NULL
        CHECK (revocation_rights_mode IN ('CA_REVOCABLE','SUBJECT_REVOCABLE','THRESHOLD','MULTI_OUTPOINT')),
    cert_txid               BYTEA CHECK (cert_txid IS NULL OR octet_length(cert_txid) = 32),
    cert_outpoint_index     INTEGER,
    cert_body_canonical_id  BIGINT NOT NULL REFERENCES evid.canonical_record(id),
    cert_body_sha256        BYTEA NOT NULL CHECK (octet_length(cert_body_sha256) = 32),
    onchain_status          TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (onchain_status IN ('PENDING','UNSPENT','SPENT','REORGED')),
    onchain_status_checked_at TIMESTAMPTZ,
    supersedes_id           BIGINT REFERENCES core.key_certificate(id),
    issued_by               BIGINT NOT NULL REFERENCES core.app_user(id),
    issued_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_from              TIMESTAMPTZ,
    valid_until             TIMESTAMPTZ,
    CONSTRAINT keycert_cp_consistent CHECK (
        (subject_kind = 'COUNTERPARTY' AND counterparty_id IS NOT NULL) OR
        (subject_kind = 'ENTITY' AND counterparty_id IS NULL))
);
CREATE INDEX keycert_subject_idx ON core.key_certificate(entity_id, subject_master_pubkey);
CREATE INDEX keycert_cp_idx ON core.key_certificate(counterparty_id);
CREATE INDEX keycert_status_idx ON core.key_certificate(entity_id, onchain_status, onchain_status_checked_at);

-- REQ-DATA-0164c: the certificate references a KEY_CERTIFICATE canonical record of
-- the same entity (structural binding; field-equality at the app/recon layers per
-- DEC-0006, the same rationale as the SHARED_ECDH address binding).
CREATE OR REPLACE FUNCTION core.fn_key_certificate_binding() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE rt TEXT; rent BIGINT;
BEGIN
    SELECT record_type, entity_id INTO rt, rent
        FROM evid.canonical_record WHERE id = NEW.cert_body_canonical_id;
    IF rt IS NULL THEN
        RAISE EXCEPTION 'key_certificate references missing canonical_record %', NEW.cert_body_canonical_id;
    END IF;
    IF rt <> 'KEY_CERTIFICATE' THEN
        RAISE EXCEPTION 'cert_body_canonical_id must be a KEY_CERTIFICATE record, got % (REQ-DATA-0195)', rt;
    END IF;
    IF rent <> NEW.entity_id THEN
        RAISE EXCEPTION 'certificate body entity % does not match certificate entity %', rent, NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_key_certificate_binding
    BEFORE INSERT OR UPDATE ON core.key_certificate
    FOR EACH ROW EXECUTE FUNCTION core.fn_key_certificate_binding();

INSERT INTO core.schema_migration(version) VALUES ('0025_key_certificate');
COMMIT;
