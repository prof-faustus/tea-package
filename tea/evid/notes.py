"""Persist engine-built notes and anchor them (Stage 5 evidence wiring).

The engine builds a SignedNote (tea/evid/bridge.build_note); the Package stores it
verbatim in evid.note (REQ-DATA-0071) bound to its canonical record, then folds an
ordered note set into a BSV-canonical Merkle root via the engine and records the
batch in evid.anchor_batch/anchor_member (REQ-DATA-0073/0074, REQ-EVID-0104). The
Package never re-implements the Merkle/commitment logic; it consumes the engine.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import text

_KIND_TO_NOTE_TYPE = {"invoice": "INVOICE_NOTE", "payment": "PAYMENT_NOTE"}


def store_note(conn, *, entity_id: int, canonical_id: int, note: dict,
               key_path: str, engine_version: str, linked_note_id: int | None = None) -> int:
    """Insert an engine SignedNote into evid.note, bound to its canonical record."""
    note_type = _KIND_TO_NOTE_TYPE[note["kind"]]
    body = bytes.fromhex(note["body_hex"])
    note_id_bytes = bytes.fromhex(note["body_hash_hex"])      # engine-assigned, unique per note
    l_tag = bytes.fromhex(note["primary_tag_hex"])
    signature = bytes.fromhex(note["signature_hex"])
    cp_pubkey = bytes.fromhex(note["counterparty_pk_hex"])
    return conn.execute(text(
        "INSERT INTO evid.note"
        "(entity_id, canonical_id, note_type, note_id_bytes, note_body, l_tag, "
        " linked_note_id, key_path, counterparty_pubkey, signature, engine_version) "
        "VALUES (:e,:c,:nt,:nid,:body,:l,:lk,:kp,:cp,:sig,:ev) RETURNING id"),
        {"e": entity_id, "c": canonical_id, "nt": note_type, "nid": note_id_bytes,
         "body": body, "l": l_tag, "lk": linked_note_id, "kp": key_path,
         "cp": cp_pubkey, "sig": signature, "ev": engine_version},
    ).scalar_one()


def _signed_note_for_anchor(row) -> dict:
    """Reconstruct the minimal SignedNote the engine `anchor` needs from a stored row.
    Anchor folds over the note body only; the other fields just need to deserialize."""
    body_hex = bytes(row.note_body).hex()
    body_hash = hashlib.sha256(hashlib.sha256(bytes(row.note_body)).digest()).hexdigest()
    kind = "invoice" if row.note_type == "INVOICE_NOTE" else "payment"
    return {
        "kind": kind, "version": 1, "note_id": "",
        "primary_tag_hex": bytes(row.l_tag).hex(), "secondary_tag_hex": "00" * 32,
        "issuer_pk_hex": "00" * 33, "counterparty_pk_hex": bytes(row.counterparty_pubkey).hex(),
        "fields_pub": [], "commitments_hex": [],
        "body_hex": body_hex, "body_hash_hex": body_hash, "signature_hex": bytes(row.signature).hex(),
    }


def anchor_stored_notes(conn, bridge, *, entity_id: int, note_ids: list[int],
                        network: str, bsv_anchor_txid_be: str, tmp_dir,
                        batch_id: int = 0) -> dict:
    """Fold the given stored notes into a Merkle root and record the batch."""
    from pathlib import Path
    rows = conn.execute(text(
        "SELECT id, note_type, note_body, l_tag, counterparty_pubkey, signature "
        "FROM evid.note WHERE id = ANY(:ids) ORDER BY id"), {"ids": note_ids}).fetchall()
    if not rows:
        raise ValueError("no notes to anchor")
    signed = [_signed_note_for_anchor(r) for r in rows]

    notes_p = Path(tmp_dir) / "anchor_notes.json"
    notes_p.write_text(json.dumps(signed), encoding="utf-8")
    batch = bridge.anchor(notes_p, Path(tmp_dir) / "anchor_batch.json",
                          bsv_anchor_txid_be=bsv_anchor_txid_be, batch_id=batch_id)

    merkle_root = bytes.fromhex(batch["merkle_root_hex"])
    batch_db_id = conn.execute(text(
        "INSERT INTO evid.anchor_batch(entity_id, merkle_root, status, network) "
        "VALUES (:e,:r,'PENDING',:n) RETURNING id"),
        {"e": entity_id, "r": merkle_root, "n": network}).scalar_one()

    for leaf_index, (r, leaf_hex) in enumerate(zip(rows, batch["leaf_hashes_hex"])):
        conn.execute(text(
            "INSERT INTO evid.anchor_member(batch_id, note_id, leaf_index, leaf_hash) "
            "VALUES (:b,:n,:i,:h)"),
            {"b": batch_db_id, "n": r.id, "i": leaf_index, "h": bytes.fromhex(leaf_hex)})
        conn.execute(text("UPDATE evid.note SET status='ANCHOR_PENDING' WHERE id=:n"),
                     {"n": r.id})

    return {"batch_id": batch_db_id, "merkle_root_hex": batch["merkle_root_hex"],
            "member_count": len(rows)}
