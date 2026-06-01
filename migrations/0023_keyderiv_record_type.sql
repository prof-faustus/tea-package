-- 0023_keyderiv_record_type — widen evid.canonical_record record_type to add
-- KEY_DERIVATION (REQ-DATA-0166). Irreversible-with-data: narrowing the CHECK
-- once any KEY_DERIVATION record exists would orphan chained records (REQ-DATA-0148).
BEGIN;

ALTER TABLE evid.canonical_record
    DROP CONSTRAINT canonical_record_record_type_check,
    ADD CONSTRAINT canonical_record_record_type_check
        CHECK (record_type IN
        ('INVOICE','PAYMENT','CREDIT_NOTE','ADJUSTMENT','STATEMENT',
         'MESSAGE','WALLET_TRANSFER','KEY_DERIVATION'));

INSERT INTO core.schema_migration(version) VALUES ('0023_keyderiv_record_type');
COMMIT;
