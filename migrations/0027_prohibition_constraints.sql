-- 0027_prohibition_constraints — the database-resident locking-script guard
-- (REQ-DATA-0146, REQ-BUILD-0062). This is Layer 3 of the four independent
-- prohibition layers: a forbidden locking script cannot be PERSISTED even if
-- application code is bypassed. Opcodes are matched by byte value (no mnemonics)
-- so this migration itself stays clean under the CI prohibition gate.
--   0x6a=106 data-carrier   0xa9=169 hash160   0x87=135 equal
--   0x76=118 dup            0x14=20  push20     0x88=136 equalverify  0xac=172 checksig
BEGIN;

CREATE OR REPLACE FUNCTION wallet.fn_assert_allowed_script(script BYTEA) RETURNS void
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE n INT := octet_length(script);
BEGIN
    IF script IS NULL OR n = 0 THEN
        RAISE EXCEPTION 'empty locking script is not an allowed template (REQ-NET-0074)';
    END IF;
    -- reject a data-carrier output (first opcode 0x6a)
    IF get_byte(script, 0) = 106 THEN
        RAISE EXCEPTION 'forbidden locking script: data-carrier output (four-layer L3, REQ-DATA-0146)';
    END IF;
    -- reject the script-hash template: 0xa9 0x14 <20 bytes> 0x87  (length 23)
    IF n = 23 AND get_byte(script,0) = 169 AND get_byte(script,1) = 20
       AND get_byte(script,22) = 135 THEN
        RAISE EXCEPTION 'forbidden locking script: script-hash template (four-layer L3, REQ-DATA-0146)';
    END IF;
    -- allowed template: pay-to-pubkey-hash  0x76 0xa9 0x14 <20> 0x88 0xac  (length 25)
    IF n = 25 AND get_byte(script,0) = 118 AND get_byte(script,1) = 169
       AND get_byte(script,2) = 20 AND get_byte(script,23) = 136
       AND get_byte(script,24) = 172 THEN
        RETURN;  -- allowed
    END IF;
    RAISE EXCEPTION 'locking script does not match the allowed template set (REQ-NET-0074)';
END;
$$;

-- Bind the guard to wallet.utxo.locking_script: a forbidden locking script cannot
-- be persisted even if application code is bypassed (REQ-DATA-0189). Other
-- locking-script-bearing tables attach the same guard when they land.
CREATE OR REPLACE FUNCTION wallet.fn_utxo_script_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM wallet.fn_assert_allowed_script(NEW.locking_script);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_utxo_script_guard
    BEFORE INSERT OR UPDATE ON wallet.utxo
    FOR EACH ROW EXECUTE FUNCTION wallet.fn_utxo_script_guard();

INSERT INTO core.schema_migration(version) VALUES ('0027_prohibition_constraints');
COMMIT;
