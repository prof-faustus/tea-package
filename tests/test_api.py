"""REST API tests: health, OpenAPI snapshot, and the evidence read/verify endpoints.

The OpenAPI document is pinned (REQ-API-0150, REQ-BUILD-0033) so an unintended
surface change is caught. The evidence endpoints are exercised against the live DB
when reachable; otherwise those tests skip.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from tea.api.app import app  # noqa: E402
from tea.evid import lineage as LIN  # noqa: E402
from tea.wire import records as R  # noqa: E402

client = TestClient(app)
OPENAPI = Path(__file__).resolve().parents[1] / "contract" / "openapi.json"


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_readyz_reports_checks():
    body = client.get("/readyz").json()
    assert "ready" in body and "engine" in body["checks"] and "db" in body["checks"]


def test_openapi_snapshot():
    spec = client.get("/openapi.json").json()
    if not OPENAPI.exists():
        OPENAPI.parent.mkdir(parents=True, exist_ok=True)
        OPENAPI.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("pinned OpenAPI snapshot created; re-run asserts against it")
    want = json.loads(OPENAPI.read_text(encoding="utf-8"))
    # paths + operationIds are the stable contract surface
    assert sorted(spec["paths"]) == sorted(want["paths"]), "API path surface drifted"


def _db_or_skip():
    try:
        eng = create_engine("postgresql+psycopg2://tea:tea@127.0.0.1:5455/tea")
        with eng.connect() as c:
            c.execute(text("SELECT 1 FROM evid.audit_chain LIMIT 1"))
        return eng
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"DB unavailable: {e}")


def test_evidence_and_chain_verify_endpoints():
    eng = _db_or_skip()
    suffix = uuid.uuid4().hex[:8]
    with eng.begin() as c:
        e_id = c.execute(text(
            "INSERT INTO core.entity(name, reporting_currency_id, base_key_ref) "
            "VALUES (:n,0,'custody://e') RETURNING id"), {"n": f"ApiCo-{suffix}"}).scalar_one()
        record = {
            R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: bytes(16),
            R.LOGICAL_KEY: f"inv:api:{suffix}", R.CREATED_AT: "2026-04-01T09:00:00.000Z",
            16: "INV-API", 17: bytes(range(1, 34)), 18: "EUR", 19: 2, 20: 12100,
            22: "2026-04-30T00:00:00.000Z", 24: [],
        }
        cid, seq, _ = LIN.record_canonical_and_chain(
            c, entity_id=e_id, logical_key=f"inv:api:{suffix}", record=record)

    r = client.get(f"/evidence/{cid}")
    assert r.status_code == 200
    body = r.json()
    assert body["record_type"] == "INVOICE"
    assert body["entity_id"] == e_id
    assert body["chain"]["seq"] == seq
    assert len(body["canonical_sha256"]) == 64

    v = client.get(f"/entities/{e_id}/chain/verify").json()
    assert v["intact"] is True and v["first_broken_seq"] is None

    assert client.get("/evidence/999999999").status_code == 404
