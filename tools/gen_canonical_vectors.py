#!/usr/bin/env python3
"""Generate the canonical-serialization reproducibility vectors (REQ-WIRE-0100/0101).

Produces `vectors/canonical_v1.json`: a set of fixture records covering each
record type, bignum amounts, multi-line invoice with mixed tax, unicode (NFC),
maximum field sizes, and empty/optional-field cases. Each vector records the
input, the expected canonical CBOR (hex), and the expected canonical SHA-256.

The `reproduce` test (`tests/test_canonical_vectors.py`) re-encodes every fixture
and diffs byte-for-byte; any drift fails CI. Re-run this generator ONLY to add
fixtures, never to silently bless a changed byte layout.
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.wire import records as R
from tea.wire.cbor import encode

ENTITY = bytes(range(16))
PK = bytes(range(1, 34))
PK2 = bytes(range(34, 67))
TX = bytes(range(32))
THREAD = bytes(range(16, 32))
WALLET = bytes(range(32, 48))


def fixtures() -> list[dict]:
    out = []

    # 1. minimal invoice (optional fields absent)
    out.append(("invoice_minimal", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "inv:ACME:2026:0001", R.CREATED_AT: "2026-04-01T09:00:00.000Z",
        16: "INV-0001", 17: PK, 18: "EUR", 19: 2, 20: 12100,
        22: "2026-04-30T00:00:00.000Z", 24: [],
    }))

    # 2. multi-line invoice with mixed tax + terms + receive address
    out.append(("invoice_multiline_mixed_tax", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "inv:ACME:2026:0002", R.CREATED_AT: "2026-04-02T10:30:00.000Z",
        16: "INV-0002", 17: PK, 18: "GBP", 19: 2, 20: 360000,
        21: [["STD", 20, 100, 250000, 50000], ["RED", 5, 100, 100000, 5000]],
        22: "2026-05-02T00:00:00.000Z", 23: "NET30",
        24: [
            [bytes(range(16)), "Consulting", 10, 1, 25000, "STD"],
            [bytes(range(16)), "Materials", 4, 1, 25000, "RED"],
        ],
        25: "1ExampleReceiveAddrAAAAAAAAAAAAAAAA",
    }))

    # 3. invoice with a bignum gross amount (beyond 64-bit)
    out.append(("invoice_bignum", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "inv:ACME:2026:0003", R.CREATED_AT: "2026-04-03T00:00:00.000Z",
        16: "INV-0003", 17: PK, 18: "JPY", 19: 0,
        20: 18446744073709551616 * 7 + 123, 22: "2026-05-03T00:00:00.000Z", 24: [],
    }))

    # 4. unicode (NFC) logical key + terms
    out.append(("invoice_unicode_nfc", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_INVOICE, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "inv:Æther-Ångström:2026:Ω", R.CREATED_AT: "2026-04-04T00:00:00.000Z",
        16: "INV-Ω-0004", 17: PK, 18: "EUR", 19: 2, 20: 1,
        22: "2026-05-04T00:00:00.000Z", 23: "café—naïve", 24: [],
    }))

    # 5. payment (BSV rail) settling an invoice
    out.append(("payment_bsv_full", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_PAYMENT, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "pay:ACME:2026:0001", R.CREATED_AT: "2026-05-02T12:00:00.000Z",
        32: "inv:ACME:2026:0001", 33: 2, 34: "", 35: 12100, 36: "EUR", 37: 2,
        38: 1, 39: TX, 40: 1,
    }))

    # 6. message record (commitment to ciphertext; no plaintext)
    out.append(("message", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_MESSAGE, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "msg:thread-1:0001", R.CREATED_AT: "2026-05-05T08:00:00.000Z",
        48: THREAD, 49: PK2, 50: TX,
    }))

    # 7. wallet transfer record
    out.append(("wallet_transfer", {
        R.SCHEMA_VERSION: 1, R.RECORD_TYPE: R.RT_WALLET_TRANSFER, R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "wxfer:0001", R.CREATED_AT: "2026-05-06T09:00:00.000Z",
        56: WALLET, 57: 1, 58: 1, 59: "", 60: 500000, 61: TX,
    }))

    return out


def main() -> int:
    import hashlib
    vectors = []
    for name, rec in fixtures():
        data = R.canonical_bytes(rec)
        vectors.append({
            "name": name,
            "record": _jsonable(rec),
            "cbor_hex": data.hex(),
            "canonical_sha256": hashlib.sha256(data).hexdigest(),
        })
    out_path = Path(__file__).resolve().parents[1] / "vectors" / "canonical_v1.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"schema_version": 1, "vectors": vectors}, indent=2) + "\n",
                        encoding="utf-8")
    print(f"wrote {len(vectors)} vectors to {out_path}")
    return 0


def _jsonable(rec: dict):
    """Represent a record for the vector file: int keys -> str, bytes -> hex tag."""
    def conv(v):
        if isinstance(v, bytes):
            return {"__bytes_hex__": v.hex()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        if isinstance(v, dict):
            return {str(k): conv(x) for k, x in v.items()}
        return v
    return {str(k): conv(v) for k, v in rec.items()}


if __name__ == "__main__":
    raise SystemExit(main())
