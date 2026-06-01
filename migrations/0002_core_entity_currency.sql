-- 0002_core_entity_currency — entities, currencies, fx, gl maps, component_version.
BEGIN;

CREATE TABLE core.component_version (        -- REQ-DATA-0143
    component   TEXT PRIMARY KEY,
    version     TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes       TEXT
);

CREATE TABLE core.entity (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL,
    legal_name      TEXT,
    jurisdiction    TEXT,
    reporting_currency_id BIGINT NOT NULL,
    base_key_ref    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','SUSPENDED','CLOSED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT entity_name_uniq UNIQUE (name)
);

CREATE TABLE core.currency (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    code        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('FIAT','BSV','TOKEN','STABLECOIN')),
    scale       SMALLINT NOT NULL CHECK (scale BETWEEN 0 AND 18),
    token_protocol TEXT,
    token_asset_id TEXT,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT currency_code_uniq UNIQUE (entity_id, code, token_protocol, token_asset_id)
);
CREATE INDEX currency_entity_idx ON core.currency(entity_id);

CREATE TABLE core.fx_rate (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES core.entity(id),
    from_currency_id BIGINT NOT NULL REFERENCES core.currency(id),
    to_currency_id   BIGINT NOT NULL REFERENCES core.currency(id),
    rate_num    BIGINT NOT NULL,
    rate_den    BIGINT NOT NULL CHECK (rate_den > 0),
    as_of       TIMESTAMPTZ NOT NULL,
    source      TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fx_rate_uniq UNIQUE (entity_id, from_currency_id, to_currency_id, as_of, source)
);
CREATE INDEX fx_entity_idx ON core.fx_rate(entity_id);
CREATE INDEX fx_from_idx ON core.fx_rate(from_currency_id);
CREATE INDEX fx_to_idx ON core.fx_rate(to_currency_id);

CREATE TABLE core.gl_entity_map (
    entity_id     BIGINT PRIMARY KEY REFERENCES core.entity(id),
    gl_entity_id  BIGINT NOT NULL
);
CREATE TABLE core.gl_currency_map (
    currency_id     BIGINT PRIMARY KEY REFERENCES core.currency(id),
    gl_currency_id  BIGINT NOT NULL
);

INSERT INTO core.schema_migration(version) VALUES ('0002_core_entity_currency');
COMMIT;
