-- 0018_seed_permissions — seed permission codes, default roles, and the default
-- role→permission mapping (REQ-DATA-0142). Idempotent.
BEGIN;

INSERT INTO authz.permission(code) VALUES
    ('INVOICE_CREATE'),('INVOICE_VIEW'),('PAYMENT_POST'),('PAYMENT_VIEW'),
    ('WALLET_VIEW'),('WALLET_SEND'),('WALLET_RECEIVE'),('WALLET_MINT'),('WALLET_BURN'),
    ('MATCH_REVIEW'),('DISCLOSE'),('REPORT_VIEW'),('MESSAGE_SEND'),('MESSAGE_READ'),
    ('USER_ADMIN'),('ENTITY_ADMIN'),('AUDIT_VIEW')
ON CONFLICT (code) DO NOTHING;

INSERT INTO core.role(name, description) VALUES
    ('ADMIN','Full administrative authority'),
    ('ACCOUNTANT','Bookkeeping, invoicing, payments, reconciliation'),
    ('AUDITOR','Read-only audit and evidence review'),
    ('TREASURER','Wallet and treasury operations'),
    ('VIEWER','Read-only access')
ON CONFLICT (name) DO NOTHING;

-- ADMIN: every permission
INSERT INTO authz.role_permission(role_id, permission_id)
    SELECT r.id, p.id FROM core.role r CROSS JOIN authz.permission p WHERE r.name='ADMIN'
ON CONFLICT DO NOTHING;

-- ACCOUNTANT
INSERT INTO authz.role_permission(role_id, permission_id)
    SELECT r.id, p.id FROM core.role r JOIN authz.permission p ON p.code IN
        ('INVOICE_CREATE','INVOICE_VIEW','PAYMENT_POST','PAYMENT_VIEW','MATCH_REVIEW',
         'REPORT_VIEW','DISCLOSE','MESSAGE_SEND','MESSAGE_READ','WALLET_VIEW','WALLET_RECEIVE')
    WHERE r.name='ACCOUNTANT'
ON CONFLICT DO NOTHING;

-- AUDITOR
INSERT INTO authz.role_permission(role_id, permission_id)
    SELECT r.id, p.id FROM core.role r JOIN authz.permission p ON p.code IN
        ('INVOICE_VIEW','PAYMENT_VIEW','WALLET_VIEW','REPORT_VIEW','AUDIT_VIEW','MESSAGE_READ')
    WHERE r.name='AUDITOR'
ON CONFLICT DO NOTHING;

-- TREASURER
INSERT INTO authz.role_permission(role_id, permission_id)
    SELECT r.id, p.id FROM core.role r JOIN authz.permission p ON p.code IN
        ('WALLET_VIEW','WALLET_SEND','WALLET_RECEIVE','WALLET_MINT','WALLET_BURN',
         'PAYMENT_VIEW','REPORT_VIEW')
    WHERE r.name='TREASURER'
ON CONFLICT DO NOTHING;

-- VIEWER
INSERT INTO authz.role_permission(role_id, permission_id)
    SELECT r.id, p.id FROM core.role r JOIN authz.permission p ON p.code IN
        ('INVOICE_VIEW','PAYMENT_VIEW','WALLET_VIEW','REPORT_VIEW')
    WHERE r.name='VIEWER'
ON CONFLICT DO NOTHING;

INSERT INTO core.schema_migration(version) VALUES ('0018_seed_permissions');
COMMIT;
