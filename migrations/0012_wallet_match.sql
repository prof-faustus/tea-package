-- 0012_wallet_match — inbound settlement matching (REQ-DATA-0090..0092).
BEGIN;

CREATE TABLE wallet.match (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id     BIGINT NOT NULL REFERENCES core.entity(id),
    transfer_id   BIGINT NOT NULL REFERENCES wallet.transfer(id),
    invoice_canonical_id BIGINT REFERENCES evid.canonical_record(id),
    match_method  TEXT NOT NULL CHECK (match_method IN
                  ('LINKAGE_TAG','UNIQUE_ADDRESS','HEURISTIC_PROPOSAL','MANUAL')),
    match_status  TEXT NOT NULL DEFAULT 'PROPOSED'
                  CHECK (match_status IN ('AUTO_CONFIRMED','PROPOSED','ACCEPTED','REJECTED','UNMATCHED')),
    applied_amount_minor BIGINT NOT NULL DEFAULT 0,
    settlement_kind TEXT CHECK (settlement_kind IN ('FULL','PARTIAL','OVERPAYMENT','UNDERPAYMENT')),
    suspense_account_id BIGINT,
    reviewed_by   BIGINT REFERENCES core.app_user(id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX match_invoice_idx ON wallet.match(invoice_canonical_id);
CREATE INDEX match_status_idx ON wallet.match(entity_id, match_status);

INSERT INTO core.schema_migration(version) VALUES ('0012_wallet_match');
COMMIT;
