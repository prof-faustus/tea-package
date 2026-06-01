-- SHARED_ECDH address persistence guards (REQ-DATA-0163/0165, REQ-WIRE-0133/0136).
-- A one-time shared address must bind to a chained KEY_DERIVATION record of the
-- same entity, carry the complete derivation context, and be unique per context.
DO $$
DECLARE
    e_id BIGINT; w_id BIGINT; cp_id BIGINT;
    kd_id BIGINT; kd_sha BYTEA; kd2_id BIGINT;
    zero32 CONSTANT BYTEA := decode(repeat('00',32),'hex');
    pk1 CONSTANT BYTEA := decode('02' || repeat('22',32), 'hex');
    pk2 CONSTANT BYTEA := decode('03' || repeat('33',32), 'hex');
    saltc CONSTANT BYTEA := decode(repeat('cc',32),'hex');
    rejected BOOLEAN;
BEGIN
    INSERT INTO core.entity(name, reporting_currency_id, base_key_ref)
        VALUES ('DerivCo', 0, 'custody://entity/deriv') RETURNING id INTO e_id;
    INSERT INTO wallet.wallet(entity_id, label, hd_root_ref, network)
        VALUES (e_id, 'w', 'custody://hd', 'REGTEST') RETURNING id INTO w_id;
    INSERT INTO core.counterparty(entity_id, display_name, counterparty_uid, master_pubkey, master_pubkey_status)
        VALUES (e_id, 'CP', decode(repeat('ab',16),'hex'), decode('02'||repeat('11',32),'hex'), 'VERIFIED')
        RETURNING id INTO cp_id;

    -- a chained KEY_DERIVATION record
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'KEY_DERIVATION', 'kd:1', '\xaa'::bytea, digest('\xaa'::bytea,'sha256'), 1)
        RETURNING id, canonical_sha256 INTO kd_id, kd_sha;
    INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
        VALUES (1, e_id, kd_id, zero32, digest(zero32 || kd_sha, 'sha256'));

    -- an UNCHAINED KEY_DERIVATION record (for the negative test)
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'KEY_DERIVATION', 'kd:2', '\xbb'::bytea, digest('\xbb'::bytea,'sha256'), 1)
        RETURNING id INTO kd2_id;

    -- POSITIVE: a SHARED_ECDH address bound to the chained KEY_DERIVATION record
    INSERT INTO wallet.address(wallet_id, entity_id, derivation_path, pubkey, address_text, purpose,
        derivation_method, counterparty_id, scheme_version, derivation_domain, invoice_number,
        payment_index, key_derivation_canonical_id, salt_commitment)
        VALUES (w_id, e_id, 'shared', pk1, 'mAddrOne', 'INVOICE',
        'SHARED_ECDH', cp_id, 1, 1, 1, 0, kd_id, saltc);

    -- NEGATIVE: binding to an UNCHAINED KEY_DERIVATION record is rejected (REQ-WIRE-0136)
    rejected := false;
    BEGIN
        INSERT INTO wallet.address(wallet_id, entity_id, derivation_path, pubkey, address_text, purpose,
            derivation_method, counterparty_id, scheme_version, derivation_domain, invoice_number,
            payment_index, key_derivation_canonical_id, salt_commitment)
            VALUES (w_id, e_id, 'shared', pk2, 'mAddrTwo', 'INVOICE',
            'SHARED_ECDH', cp_id, 1, 1, 2, 0, kd2_id, saltc);
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: binding to unchained KEY_DERIVATION not rejected'; END IF;

    -- NEGATIVE: incomplete SHARED_ECDH context (missing counterparty_id) is rejected (REQ-DATA-0163)
    rejected := false;
    BEGIN
        INSERT INTO wallet.address(wallet_id, entity_id, derivation_path, pubkey, address_text, purpose,
            derivation_method, scheme_version, derivation_domain, invoice_number, payment_index,
            key_derivation_canonical_id, salt_commitment)
            VALUES (w_id, e_id, 'shared', pk2, 'mAddrThree', 'INVOICE',
            'SHARED_ECDH', 1, 1, 3, 0, kd_id, saltc);
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: incomplete SHARED_ECDH context not rejected'; END IF;

    -- NEGATIVE: duplicate derivation context is rejected (REQ-WIRE-0133 one-time guarantee)
    rejected := false;
    BEGIN
        INSERT INTO wallet.address(wallet_id, entity_id, derivation_path, pubkey, address_text, purpose,
            derivation_method, counterparty_id, scheme_version, derivation_domain, invoice_number,
            payment_index, key_derivation_canonical_id, salt_commitment)
            VALUES (w_id, e_id, 'shared', pk2, 'mAddrFour', 'INVOICE',
            'SHARED_ECDH', cp_id, 1, 1, 1, 0, kd_id, saltc);   -- same (cp,scheme,domain,invoice,index) as mAddrOne
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: duplicate derivation context not rejected'; END IF;

    RAISE NOTICE 'ALL-DERIVATION-PERSISTENCE-TESTS-PASSED entity=%', e_id;
END;
$$;
