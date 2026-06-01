-- 0020_counterparty_inv_seq — sequential per-counterparty invoice numbering (REQ-DATA-0161).
BEGIN;

CREATE TABLE core.counterparty_invoice_seq (
    entity_id       BIGINT NOT NULL REFERENCES core.entity(id),
    counterparty_id BIGINT NOT NULL REFERENCES core.counterparty(id),
    next_invoice_number BIGINT NOT NULL DEFAULT 1 CHECK (next_invoice_number >= 1),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, counterparty_id)
);

INSERT INTO core.schema_migration(version) VALUES ('0020_counterparty_inv_seq');
COMMIT;
