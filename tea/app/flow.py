"""Evidenced monetary events: a GL posting tied to its full cryptographic evidence.

issue_evidenced_invoice posts a ClientInvoice through python-accounting (the GL is
authoritative for money, REQ-DATA-0251), then in one evidence transaction records
the canonical INVOICE record, appends the audit chain, links the lineage row to the
GL transaction id, builds the engine invoice note, stores it, and advances the
lineage state POSTED→NOTE_BUILT. The GL posting is never blocked by an evidence-layer
failure (REQ-DATA-0251); the lineage records the evidence state separately.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text

from tea.wire import records as R
from tea.evid import lineage as LIN, notes as NOTES


def issue_evidenced_invoice(*, gl, evid_conn, bridge, core_entity_id: int,
                            client_account, revenue_account, lines: list[dict],
                            narration: str, tax=None,
                            entity_uid: bytes, counterparty_uid: bytes,
                            invoice_number: int, invoice_pubkey: bytes,
                            issuer_sk_hex: str, counterparty_pub_hex: str,
                            note_fields: list[dict], created_at: str,
                            logical_key: str, tmp_dir, engine_version: str) -> dict:
    """Post the invoice (GL) + record its evidence (canonical/chain/note/lineage).

    `gl` is a GLService (scoped GL session); `evid_conn` is a SQLAlchemy connection
    in an open transaction for the Package schemas (core/evid). Returns the GL txn id
    and the evidence ids.
    """
    # 1. GL posting (authoritative for money)
    gl_lines = [{"account": revenue_account, "amount": ln["amount"],
                 "quantity": ln.get("quantity", 1), "tax": tax} for ln in lines]
    inv = gl.post_client_invoice(client_account=client_account, lines=gl_lines,
                                 narration=narration)
    gl_txn_id = int(inv.id)
    gross_minor = int(Decimal(inv.amount) * 100)   # EUR scale 2 → minor units

    # 2. canonical INVOICE record built from the library-computed gross
    record = {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE,
        R.ENTITY_UID: entity_uid, R.LOGICAL_KEY: logical_key, R.CREATED_AT: created_at,
        16: f"INV-{invoice_number}", 17: invoice_pubkey, 18: "EUR", 19: 2,
        20: gross_minor, 22: "2026-04-30T00:00:00.000Z", 24: [],
    }
    canonical_id, audit_seq, _ = LIN.record_canonical_and_chain(
        evid_conn, entity_id=core_entity_id, logical_key=logical_key, record=record)

    # 3. lineage POSTED, tying the GL txn to the canonical record + chain entry
    lineage_id = LIN.link_lineage(
        evid_conn, entity_id=core_entity_id, canonical_id=canonical_id,
        audit_seq=audit_seq, gl_txn_id=gl_txn_id, state="POSTED")

    # 4. engine invoice note (values stay private), bound to the canonical record
    note = bridge.build_note(
        sk_hex=issuer_sk_hex, counterparty_pub_hex=counterparty_pub_hex,
        note_id=logical_key, fields=note_fields, kind="invoice",
        fields_path=tmp_dir / "flow_fields.json", out_path=tmp_dir / "flow_note.json")
    note_db_id = NOTES.store_note(
        evid_conn, entity_id=core_entity_id, canonical_id=canonical_id, note=note,
        key_path=f"m/0/{invoice_number}", engine_version=engine_version)

    # 5. advance lineage POSTED → NOTE_BUILT
    evid_conn.execute(text(
        "UPDATE evid.lineage SET state='NOTE_BUILT', note_id=:n, updated_at=now() "
        "WHERE id=:l"), {"n": note_db_id, "l": lineage_id})

    return {
        "gl_txn_id": gl_txn_id, "gross_minor": gross_minor,
        "canonical_id": canonical_id, "audit_seq": audit_seq,
        "lineage_id": lineage_id, "note_id": note_db_id,
        "l_tag_hex": note["primary_tag_hex"],
    }
