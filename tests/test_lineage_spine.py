"""Lineage spine integration: a GL posting ties to a canonical record + chain entry.

REQ-DATA-0023/0072/0250: for the GL transaction the Package triggers, there is a
corresponding canonical record, an audit-chain entry, and an evid.lineage row
joining gl_txn_id <-> canonical_id <-> audit_seq. The DB triggers re-validate the
canonical sha and the chain linkage; fn_verify_chain confirms integrity.
"""
from __future__ import annotations

import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("python_accounting")
pytest.importorskip("sqlalchemy")

from sqlalchemy import create_engine, text  # noqa: E402
from python_accounting.models import Base  # noqa: E402
from tea.gl.engine import make_engine, session_for, dsn  # noqa: E402
from tea.gl.service import GLService, AccountType  # noqa: E402
from tea.evid import lineage as LIN  # noqa: E402
from tea.wire import records as R  # noqa: E402


def _engines_or_skip():
    try:
        gl_eng = make_engine()
        Base.metadata.create_all(gl_eng)
        core_eng = create_engine(dsn())
        with core_eng.connect() as c:
            c.execute(text("SELECT 1 FROM evid.audit_chain LIMIT 1"))   # migrations applied?
        return gl_eng, core_eng
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"GL DB / migrations unavailable: {e}")


def _invoice_record(gross_minor: int, lk: str) -> dict:
    return {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE,
        R.ENTITY_UID: bytes(16), R.LOGICAL_KEY: lk,
        R.CREATED_AT: "2026-04-01T09:00:00.000Z",
        16: "INV-LIN-1", 17: bytes(range(1, 34)), 18: "EUR", 19: 2,
        20: gross_minor, 22: "2026-04-30T00:00:00.000Z", 24: [],
    }


def test_gl_posting_ties_to_canonical_and_chain():
    gl_eng, core_eng = _engines_or_skip()

    # a fresh Package-side core.entity (own chain)
    suffix = uuid.uuid4().hex[:8]
    with core_eng.begin() as c:
        core_entity_id = c.execute(text(
            "INSERT INTO core.entity(name, reporting_currency_id, base_key_ref) "
            "VALUES (:n, 0, 'custody://entity/lin') RETURNING id"),
            {"n": f"ACME-LIN-{suffix}"}).scalar_one()

    # post a GL invoice through the library -> gl_txn_id + library-computed gross
    with session_for(gl_eng) as s:
        gl = GLService.bootstrap_entity(s, f"ACME-LIN-gl-{suffix}", "EUR")
        receivable = gl.account("Trade Debtors", AccountType.RECEIVABLE)
        revenue = gl.account("Sales", AccountType.OPERATING_REVENUE)
        taxctl = gl.account("VAT Control", AccountType.CONTROL)
        vat = gl.tax("VAT20", "VAT20", 20, taxctl)
        inv = gl.post_client_invoice(
            client_account=receivable,
            lines=[{"account": revenue, "amount": 100, "quantity": 1, "tax": vat}],
            narration="INV-LIN-1")
        gl_txn_id = inv.id
        gross_minor = int(Decimal(inv.amount) * 100)   # EUR scale 2 -> minor units
    assert gross_minor == 12000

    lk = f"inv:lin:{suffix}"
    record = _invoice_record(gross_minor, lk)

    # record canonical + chain, then the lineage join
    with core_eng.begin() as c:
        cid, seq, entry = LIN.record_canonical_and_chain(
            c, entity_id=core_entity_id, logical_key=lk, record=record)
        lid = LIN.link_lineage(
            c, entity_id=core_entity_id, canonical_id=cid, audit_seq=seq,
            gl_txn_id=gl_txn_id)

    with core_eng.connect() as c:
        # chain intact
        assert LIN.verify_chain(c, core_entity_id) is None
        # lineage joins gl txn <-> canonical <-> chain
        row = c.execute(text(
            "SELECT gl_txn_id, canonical_id, audit_seq FROM evid.lineage WHERE id=:l"),
            {"l": lid}).first()
        assert row.gl_txn_id == gl_txn_id
        assert row.canonical_id == cid
        assert row.audit_seq == seq
        # the chain entry the trigger accepted matches what we computed
        ah = c.execute(text(
            "SELECT entry_hash FROM evid.audit_chain WHERE entity_id=:e AND seq=:s"),
            {"e": core_entity_id, "s": seq}).scalar()
        assert bytes(ah) == entry
        # the canonical sha was re-validated by the trigger (insert succeeded)
        stored = c.execute(text(
            "SELECT canonical_sha256 FROM evid.canonical_record WHERE id=:c"),
            {"c": cid}).scalar()
        assert len(bytes(stored)) == 32
