-- Audit-chain & canonical-record trigger tests (TEST-DATA-0001..0006/0050..0055).
-- Self-asserting: positive inserts must succeed; every prohibited operation must
-- be rejected by its trigger. Any unmet expectation RAISEs and fails the run.
DO $$
DECLARE
    e_id   BIGINT;
    cur_id BIGINT;
    c1 BIGINT; c2 BIGINT;
    sha1 BYTEA; sha2 BYTEA;
    entry1 BYTEA;
    zero32 CONSTANT BYTEA := decode(repeat('00',32),'hex');
    rejected BOOLEAN;
    broken BIGINT;
BEGIN
    -- ---- setup: entity + currency ----
    INSERT INTO core.entity(name, reporting_currency_id, base_key_ref)
        VALUES ('TestCo', 0, 'custody://entity/testco') RETURNING id INTO e_id;
    INSERT INTO core.currency(entity_id, code, kind, scale)
        VALUES (e_id, 'EUR', 'FIAT', 2) RETURNING id INTO cur_id;

    -- ---- TEST-DATA-0001: canonical insert with correct sha succeeds ----
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'INVOICE', 'inv:1', '\xdeadbeef'::bytea, digest('\xdeadbeef'::bytea,'sha256'), 1)
        RETURNING id, canonical_sha256 INTO c1, sha1;

    -- TEST-DATA-0002: canonical insert with WRONG sha is rejected (REQ-DATA-0030)
    rejected := false;
    BEGIN
        INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
            VALUES (e_id, 'INVOICE', 'inv:bad', '\xdeadbeef'::bytea, digest('\xcafe'::bytea,'sha256'), 1);
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: wrong canonical_sha256 was not rejected'; END IF;

    -- TEST-DATA-0003: canonical UPDATE/DELETE rejected (REQ-DATA-0031)
    rejected := false;
    BEGIN UPDATE evid.canonical_record SET logical_key='x' WHERE id=c1;
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: canonical UPDATE was not rejected'; END IF;
    rejected := false;
    BEGIN DELETE FROM evid.canonical_record WHERE id=c1;
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: canonical DELETE was not rejected'; END IF;

    -- second canonical record for chaining
    INSERT INTO evid.canonical_record(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version)
        VALUES (e_id, 'PAYMENT', 'pay:1', '\xfeedface'::bytea, digest('\xfeedface'::bytea,'sha256'), 1)
        RETURNING id, canonical_sha256 INTO c2, sha2;

    -- ---- TEST-DATA-0004: append seq 1 and 2 with correct linkage succeeds ----
    INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
        VALUES (1, e_id, c1, zero32, digest(zero32 || sha1, 'sha256'));
    SELECT entry_hash INTO entry1 FROM evid.audit_chain WHERE entity_id=e_id AND seq=1;
    INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
        VALUES (2, e_id, c2, entry1, digest(entry1 || sha2, 'sha256'));

    -- TEST-DATA-0005a: a gap in seq is rejected (REQ-DATA-0032)
    rejected := false;
    BEGIN
        INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
            VALUES (4, e_id, c1, (SELECT entry_hash FROM evid.audit_chain WHERE entity_id=e_id AND seq=2),
                    digest('x','sha256'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: seq gap was not rejected'; END IF;

    -- TEST-DATA-0005b: wrong prev_hash is rejected (REQ-DATA-0034)
    rejected := false;
    BEGIN
        INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
            VALUES (3, e_id, c1, zero32, digest(zero32 || sha1, 'sha256'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: wrong prev_hash was not rejected'; END IF;

    -- TEST-DATA-0005c: wrong entry_hash is rejected (REQ-DATA-0033)
    rejected := false;
    BEGIN
        INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash)
            VALUES (3, e_id, c1,
                    (SELECT entry_hash FROM evid.audit_chain WHERE entity_id=e_id AND seq=2),
                    digest('not-the-right-entry','sha256'));
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: wrong entry_hash was not rejected'; END IF;

    -- TEST-DATA-0006: audit UPDATE/DELETE rejected (REQ-DATA-0035)
    rejected := false;
    BEGIN UPDATE evid.audit_chain SET entry_hash=zero32 WHERE entity_id=e_id AND seq=1;
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: audit UPDATE was not rejected'; END IF;
    rejected := false;
    BEGIN DELETE FROM evid.audit_chain WHERE entity_id=e_id AND seq=1;
    EXCEPTION WHEN OTHERS THEN rejected := true; END;
    IF NOT rejected THEN RAISE EXCEPTION 'TEST-FAIL: audit DELETE was not rejected'; END IF;

    -- TEST-DATA-0050: fn_verify_chain returns NULL on an intact chain (REQ-DATA-0045)
    broken := evid.fn_verify_chain(e_id);
    IF broken IS NOT NULL THEN RAISE EXCEPTION 'TEST-FAIL: intact chain reported broken at seq %', broken; END IF;

    RAISE NOTICE 'ALL-CHAIN-TESTS-PASSED entity=% records=2 chain_len=2', e_id;
END;
$$;
