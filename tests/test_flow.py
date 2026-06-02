"""Capstone: an evidenced invoice — GL posting tied to canonical+chain+note+lineage.

issue_evidenced_invoice posts a ClientInvoice (library-computed tax → gross 120),
records the canonical INVOICE record + audit-chain entry, builds the engine invoice
note (values private), stores it, and links the lineage row gl_txn_id ↔ canonical_id
↔ note_id with state NOTE_BUILT. Skips when engine/DB unavailable.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("python_accounting")
pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from python_accounting.models import Base  # noqa: E402
from tea.evid.bridge import Bridge, EngineError  # noqa: E402
from tea.evid import lineage as LIN  # noqa: E402
from tea.gl.engine import make_engine, session_for, dsn  # noqa: E402
from tea.gl.service import GLService, AccountType  # noqa: E402
from tea.app.flow import issue_evidenced_invoice  # noqa: E402


def _setup_or_skip():
    b = Bridge()
    try:
        b.version()
        gl_eng = make_engine()
        Base.metadata.create_all(gl_eng)
        core_eng = create_engine(dsn())
        with core_eng.connect() as c:
            c.execute(text("SELECT 1 FROM evid.note LIMIT 1"))
    except EngineError as e:
        pytest.skip(f"engine not runnable: {e}")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"GL DB/migrations unavailable: {e}")
    return b, gl_eng, core_eng


def test_issue_evidenced_invoice(tmp_path):
    b, gl_eng, core_eng = _setup_or_skip()
    we = b.worked_example()
    sk_a, pk_b = we["sk_a_1_hex"], we["pk_b_1_hex"]
    ver = b.version()
    suffix = uuid.uuid4().hex[:8]

    with core_eng.begin() as c:
        core_eid = c.execute(text(
            "INSERT INTO core.entity(name, reporting_currency_id, base_key_ref) "
            "VALUES (:n,0,'custody://e') RETURNING id"), {"n": f"FlowCo-{suffix}"}).scalar_one()

    with session_for(gl_eng) as s:
        gl = GLService.bootstrap_entity(s, f"FlowGL-{suffix}", "EUR")
        receivable = gl.account("Trade Debtors", AccountType.RECEIVABLE)
        revenue = gl.account("Sales", AccountType.OPERATING_REVENUE)
        taxctl = gl.account("VAT Control", AccountType.CONTROL)
        vat = gl.tax("VAT20", "VAT20", 20, taxctl)

        with core_eng.begin() as ev:
            res = issue_evidenced_invoice(
                gl=gl, evid_conn=ev, bridge=b, core_entity_id=core_eid,
                client_account=receivable, revenue_account=revenue,
                lines=[{"amount": 100, "quantity": 1}], narration="INV-FLOW", tax=vat,
                entity_uid=bytes(16), counterparty_uid=bytes(range(16)),
                invoice_number=1, invoice_pubkey=bytes.fromhex(pk_b),
                issuer_sk_hex=sk_a, counterparty_pub_hex=pk_b,
                note_fields=[{"label": "Gross", "value": "12100"}],
                created_at="2026-04-01T09:00:00.000Z",
                logical_key=f"inv:flow:{suffix}", tmp_dir=tmp_path, engine_version=ver)

    assert res["gross_minor"] == 12000           # net 100 + 20% tax = 120.00

    with core_eng.connect() as c:
        row = c.execute(text(
            "SELECT state, gl_txn_id, canonical_id, audit_seq, note_id "
            "FROM evid.lineage WHERE id=:l"), {"l": res["lineage_id"]}).first()
        assert row.state == "NOTE_BUILT"
        assert row.gl_txn_id == res["gl_txn_id"]
        assert row.canonical_id == res["canonical_id"]
        assert row.audit_seq == res["audit_seq"]
        assert row.note_id == res["note_id"]
        # the note is an INVOICE_NOTE bound to that canonical record
        n = c.execute(text(
            "SELECT note_type, canonical_id FROM evid.note WHERE id=:n"),
            {"n": res["note_id"]}).first()
        assert n.note_type == "INVOICE_NOTE"
        assert n.canonical_id == res["canonical_id"]
        # the canonical record is an INVOICE chained for this entity
        rt = c.execute(text("SELECT record_type FROM evid.canonical_record WHERE id=:c"),
                       {"c": res["canonical_id"]}).scalar()
        assert rt == "INVOICE"
        assert LIN.verify_chain(c, core_eid) is None
