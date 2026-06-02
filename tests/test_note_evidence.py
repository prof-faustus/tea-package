"""Stage-5 note-evidence persistence: build-note -> evid.note -> anchor -> anchor_batch.

The engine builds a signed invoice note; the Package stores it in evid.note bound to
a chained canonical record, then folds it into a Merkle root via the engine and
records evid.anchor_batch + evid.anchor_member (REQ-DATA-0071/0073, REQ-EVID-0104).
Skips when the engine/DB is unavailable.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, text  # noqa: E402
from tea.evid.bridge import Bridge, EngineError  # noqa: E402
from tea.evid import lineage as LIN, notes as NOTES  # noqa: E402
from tea.gl.engine import dsn  # noqa: E402
from tea.wire import records as R  # noqa: E402


def _setup_or_skip():
    b = Bridge()
    try:
        b.version()
    except EngineError as e:
        pytest.skip(f"engine not runnable: {e}")
    try:
        eng = create_engine(dsn())
        with eng.connect() as c:
            c.execute(text("SELECT 1 FROM evid.note LIMIT 1"))
            c.execute(text("SELECT 1 FROM evid.anchor_batch LIMIT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"DB/migrations unavailable: {e}")
    return b, eng


def _invoice_record(lk: str, pk33: bytes) -> dict:
    return {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: bytes(16),
        R.LOGICAL_KEY: lk, R.CREATED_AT: "2026-04-01T09:00:00.000Z",
        16: "INV-EVID", 17: pk33, 18: "EUR", 19: 2, 20: 12100,
        22: "2026-04-30T00:00:00.000Z", 24: [],
    }


def test_build_store_and_anchor_invoice_note(tmp_path):
    b, eng = _setup_or_skip()
    we = b.worked_example()
    sk_a, pk_b = we["sk_a_1_hex"], we["pk_b_1_hex"]
    ver = b.version()

    note = b.build_note(sk_hex=sk_a, counterparty_pub_hex=pk_b, note_id="INV-EVID",
                        fields=[{"label": "Gross", "value": "12100"}], kind="invoice",
                        fields_path=tmp_path / "f.json", out_path=tmp_path / "note.json")

    suffix = uuid.uuid4().hex[:8]
    with eng.begin() as c:
        e_id = c.execute(text(
            "INSERT INTO core.entity(name, reporting_currency_id, base_key_ref) "
            "VALUES (:n,0,'custody://e') RETURNING id"), {"n": f"NoteEvid-{suffix}"}).scalar_one()
        # chained canonical INVOICE record the note attests
        cid, seq, _ = LIN.record_canonical_and_chain(
            c, entity_id=e_id, logical_key=f"inv:{suffix}",
            record=_invoice_record(f"inv:{suffix}", bytes.fromhex(pk_b)))
        # store the engine note bound to that canonical record
        note_db_id = NOTES.store_note(
            c, entity_id=e_id, canonical_id=cid, note=note,
            key_path="m/0/1", engine_version=ver)
        # anchor it
        res = NOTES.anchor_stored_notes(
            c, b, entity_id=e_id, note_ids=[note_db_id], network="REGTEST",
            bsv_anchor_txid_be="ab" * 32, tmp_dir=tmp_path)

    assert res["member_count"] == 1
    with eng.connect() as c:
        n = c.execute(text(
            "SELECT note_type, octet_length(note_body) nb, octet_length(l_tag) lt, "
            "status, engine_version FROM evid.note WHERE id=:i"), {"i": note_db_id}).first()
        assert n.note_type == "INVOICE_NOTE"
        assert n.nb > 0 and n.lt == 32
        assert n.status == "ANCHOR_PENDING"
        assert n.engine_version == ver
        ab = c.execute(text(
            "SELECT octet_length(merkle_root) mr, status, network FROM evid.anchor_batch "
            "WHERE id=:i"), {"i": res["batch_id"]}).first()
        assert ab.mr == 32 and ab.status == "PENDING" and ab.network == "REGTEST"
        am = c.execute(text(
            "SELECT leaf_index, octet_length(leaf_hash) lh FROM evid.anchor_member "
            "WHERE batch_id=:b AND note_id=:n"), {"b": res["batch_id"], "n": note_db_id}).first()
        assert am.leaf_index == 0 and am.lh == 32
        # the note is bound to a chained canonical record
        assert LIN.verify_chain(c, e_id) is None
