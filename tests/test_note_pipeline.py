"""Stage-5 note evidence via the engine bridge: build-note -> anchor -> prove -> verify.

A real signed invoice note is constructed by the engine (per-field commitments,
linkage tag, body, signature; field VALUES stay private), then anchored into a
BSV-canonical Merkle root, proved, and verified (REQ-EVID-0100/0101/0104). A
payment note binds its L_pay to the invoice's L_inv. Skips if the engine is not
runnable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.evid.bridge import Bridge, EngineError  # noqa: E402


def _bridge_or_skip():
    b = Bridge()
    try:
        b.version()
        return b
    except EngineError as e:
        pytest.skip(f"engine not runnable here: {e}")


def _keys(b):
    we = b.worked_example()
    return we["sk_a_1_hex"], we["pk_a_1_hex"], we["sk_b_1_hex"], we["pk_b_1_hex"]


def test_build_invoice_note_anchor_prove_verify(tmp_path):
    b = _bridge_or_skip()
    sk_a, _, _, pk_b = _keys(b)
    fields = [{"label": "InvID", "value": "INV-1"},
              {"label": "Gross", "value": "12100"},
              {"label": "Curr", "value": "EUR"}]
    note = b.build_note(sk_hex=sk_a, counterparty_pub_hex=pk_b, note_id="INV-1",
                        fields=fields, kind="invoice",
                        fields_path=tmp_path / "fields.json",
                        out_path=tmp_path / "note.json")

    # values are private: labels present, values blank; one commitment per field
    assert [f["label"] for f in note["fields_pub"]] == ["InvID", "Gross", "Curr"]
    assert all(f["value"] == "" for f in note["fields_pub"])
    assert len(note["commitments_hex"]) == 3
    assert len(note["primary_tag_hex"]) == 64                 # L_inv linkage tag
    assert note["secondary_tag_hex"] == "00" * 32             # invoice: zeros
    assert note["kind"] == "invoice"

    # anchor -> prove -> verify the real note
    (tmp_path / "notes.json").write_text(json.dumps([note]), encoding="utf-8")
    batch = b.anchor(tmp_path / "notes.json", tmp_path / "batch.json",
                     bsv_anchor_txid_be="ab" * 32)
    assert len(batch["merkle_root_hex"]) == 64
    b.prove(tmp_path / "batch.json", tmp_path / "notes.json", 0, tmp_path / "bundle.json")
    assert b.verify(tmp_path / "bundle.json") is True


def test_payment_note_binds_to_invoice_linkage(tmp_path):
    b = _bridge_or_skip()
    sk_a, pk_a, sk_b, pk_b = _keys(b)
    # invoice note from A to B
    inv = b.build_note(sk_hex=sk_a, counterparty_pub_hex=pk_b, note_id="INV-2",
                       fields=[{"label": "Gross", "value": "5000"}], kind="invoice",
                       fields_path=tmp_path / "fi.json", out_path=tmp_path / "inv.json")
    # payment note from B to A (same shared secret S) for the same parties
    pay = b.build_note(sk_hex=sk_b, counterparty_pub_hex=pk_a, note_id="PAY-2",
                       fields=[{"label": "Amount", "value": "5000"}], kind="payment",
                       fields_path=tmp_path / "fp.json", out_path=tmp_path / "pay.json")
    # the payment note's secondary tag is L_inv (the linkage to the invoice) and
    # equals the invoice note's primary tag under the shared S.
    assert pay["kind"] == "payment"
    assert pay["secondary_tag_hex"] != "00" * 32
    assert pay["secondary_tag_hex"] == inv["primary_tag_hex"]
