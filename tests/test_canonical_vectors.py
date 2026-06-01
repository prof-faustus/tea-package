"""Canonical-serialization reproducibility gate (REQ-WIRE-0100/0101, REQ-BUILD-0031).

Re-encodes every committed fixture and diffs byte-for-byte against the frozen
CBOR hex + canonical SHA-256. Any drift in the byte layout fails CI. Mirrors the
engine's own `reproduce` gate, extended to the Package's canonical layer.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.wire import records as R  # noqa: E402

VECTORS = Path(__file__).resolve().parents[1] / "vectors" / "canonical_v1.json"


def _from_jsonable(obj):
    if isinstance(obj, dict):
        if "__bytes_hex__" in obj and len(obj) == 1:
            return bytes.fromhex(obj["__bytes_hex__"])
        return {int(k): _from_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_jsonable(x) for x in obj]
    return obj


def _load():
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    return data["vectors"]


@pytest.mark.parametrize("vec", _load(), ids=lambda v: v["name"])
def test_canonical_vector_reproduces(vec):
    record = _from_jsonable(vec["record"])
    data = R.canonical_bytes(record)
    assert data.hex() == vec["cbor_hex"], f"CBOR drift for {vec['name']}"
    assert hashlib.sha256(data).hexdigest() == vec["canonical_sha256"], f"sha256 drift for {vec['name']}"


def test_vectors_cover_each_record_type():
    names = {v["name"] for v in _load()}
    # invoice, payment, message, wallet-transfer are exercised; bignum + unicode covered.
    assert any("invoice" in n for n in names)
    assert any("payment" in n for n in names)
    assert "message" in names
    assert "wallet_transfer" in names
    assert "invoice_bignum" in names
    assert "invoice_unicode_nfc" in names
