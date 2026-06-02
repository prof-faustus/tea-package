-- Stage-4 guards: the DB locking-script prohibition (Layer 3) + certificate binding.
DO $$
DECLARE
    e_id BIGINT; u_id BIGINT; kc_id BIGINT; inv_id BIGINT; cert_id BIGINT;
    pk33 CONSTANT BYTEA := decode('02' || repeat('11',32), 'hex');
    sha32 CONSTANT BYTEA := decode(repeat('cc',32), 'hex');
    rejected BOOLEAN;
BEGIN
    -- ---- Layer-3 locking-script guard (REQ-DATA-0146) ----
    -- allowed: pay-to-pubkey-hash template
    PERFORM wallet.fn_assert_allowed_script(decode('76a914' || repeat('11',20) || '88ac', 'hex'));
    -- forbidden: data-carrier output (first opcode 0x6a)
    rejected := false;
    BEGIN PERFORM wallet.fn_assert_allowed_script(decode('6a04deadbeef', 'hex'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: data-carrier output not rejected'; END IF;
    -- forbidden: script-hash template (0xa9 0x14 <20> 0x87)
    rejected := false;
    BEGIN PERFORM wallet.fn_assert_allowed_script(decode('a914' || repeat('22',20) || '87', 'hex'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: script-hash template not rejected'; END IF;
    -- forbidden: unknown template
    rejected := false;
    BEGIN PERFORM wallet.fn_assert_allowed_script(decode('0011223344', 'hex'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: unknown template not rejected'; END IF;

    -- ---- certificate binding (REQ-DATA-0164c/0195) ----
    INSERT INTO core.entity(name, reporting_currency_id, base_key_ref)
        VALUES ('CACo', 0, 'custody://ca') RETURNING id INTO e_id;
    INSERT INTO core.app_user(username, email, auth_ref)
        VALUES ('ca-' || e_id, 'ca' || e_id || '@x', 'auth://ca') RETURNING id INTO u_id;
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'KEY_CERTIFICATE', 'cert:1', '\xaa'::bytea, digest('\xaa'::bytea,'sha256'), 1)
        RETURNING id INTO kc_id;
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'INVOICE', 'inv:x', '\xbb'::bytea, digest('\xbb'::bytea,'sha256'), 1)
        RETURNING id INTO inv_id;

    -- positive: ENTITY-subject certificate bound to a KEY_CERTIFICATE record
    INSERT INTO core.key_certificate(entity_id, subject_kind, subject_master_pubkey,
        revocation_rights_mode, cert_body_canonical_id, cert_body_sha256, issued_by)
        VALUES (e_id, 'ENTITY', pk33, 'CA_REVOCABLE', kc_id, sha32, u_id) RETURNING id INTO cert_id;

    -- negative: binding to a non-KEY_CERTIFICATE record is rejected
    rejected := false;
    BEGIN
        INSERT INTO core.key_certificate(entity_id, subject_kind, subject_master_pubkey,
            revocation_rights_mode, cert_body_canonical_id, cert_body_sha256, issued_by)
            VALUES (e_id, 'ENTITY', pk33, 'CA_REVOCABLE', inv_id, sha32, u_id);
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: cert bound to non-KEY_CERTIFICATE not rejected'; END IF;

    -- negative: COUNTERPARTY subject_kind without counterparty_id is rejected (CHECK)
    rejected := false;
    BEGIN
        INSERT INTO core.key_certificate(entity_id, subject_kind, subject_master_pubkey,
            revocation_rights_mode, cert_body_canonical_id, cert_body_sha256, issued_by)
            VALUES (e_id, 'COUNTERPARTY', pk33, 'CA_REVOCABLE', kc_id, sha32, u_id);
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: COUNTERPARTY cert without counterparty_id not rejected'; END IF;

    RAISE NOTICE 'ALL-CA-TESTS-PASSED entity=%', e_id;
END;
$$;
