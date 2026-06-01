"""Stage-5 anchoring pipeline via the engine bridge: anchor -> prove -> verify.

Exercises the engine's Layer-A Merkle anchoring (REQ-WIRE-0080, REQ-EVID-0104/0105)
through C-EVID: fold note bodies into a BSV-canonical Merkle root, build an
inclusion proof for one note, and verify it. A tampered body fails verification.
Skips cleanly when the engine is not runnable. Note construction itself is an
engine operation not yet exposed by the pinned CLI (DEC-0004); here we exercise
the anchoring surface that IS exposed, with synthetic note bodies.
"""
from __future__ import annotations

import hashlib
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


def _dsha256(body_hex: str) -> str:
    b = bytes.fromhex(body_hex)
    return hashlib.sha256(hashlib.sha256(b).digest()).hexdigest()


def _note(body_hex: str, note_id: str) -> dict:
    return {
        "kind": "invoice", "version": 1, "note_id": note_id,
        "primary_tag_hex": "11" * 32, "secondary_tag_hex": "00" * 32,
        "issuer_pk_hex": "02" + "11" * 32, "counterparty_pk_hex": "03" + "22" * 32,
        "fields_pub": [], "commitments_hex": [],
        "body_hex": body_hex, "body_hash_hex": _dsha256(body_hex),
        "signature_hex": "00" * 64,
    }


def test_anchor_prove_verify(tmp_path):
    b = _bridge_or_skip()
    notes = [
        _note("deadbeef" + "00" * 28, "n0"),
        _note("feedface" + "11" * 28, "n1"),
        _note("0badf00d" + "22" * 28, "n2"),
    ]
    notes_p = tmp_path / "notes.json"
    notes_p.write_text(json.dumps(notes), encoding="utf-8")

    batch = b.anchor(notes_p, tmp_path / "batch.json", bsv_anchor_txid_be="ab" * 32)
    assert len(batch["merkle_root_hex"]) == 64
    assert len(batch["leaf_hashes_hex"]) == 3

    b.prove(tmp_path / "batch.json", notes_p, 1, tmp_path / "bundle.json")
    assert b.verify(tmp_path / "bundle.json") is True

    # tamper: a bundle whose note body is not the proven leaf must NOT verify
    bundle = json.loads((tmp_path / "bundle.json").read_text(encoding="utf-8"))
    bundle["note_body_hex"] = "ff" * 32
    bad = tmp_path / "bad_bundle.json"
    bad.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(EngineError):
        b.verify(bad)
