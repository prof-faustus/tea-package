"""Canonical-record validation, hashing, and chain-entry tests (section 04)."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.wire import records as R  # noqa: E402
from tea.wire.cbor import CanonicalError, decode  # noqa: E402

PK = bytes(range(33))            # 33-byte pseudo-pubkey
TX = bytes(range(32))            # 32-byte pseudo-txid
ENTITY = bytes(range(16))


def invoice():
    return {
        R.SCHEMA_VERSION: 1,
        R.RECORD_TYPE: R.RT_INVOICE,
        R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "inv:ACME:2026:0001",
        R.CREATED_AT: "2026-04-01T09:00:00.000Z",
        16: "INV-0001",
        17: PK,
        18: "EUR",
        19: 2,
        20: 12100,
        22: "2026-04-30T00:00:00.000Z",
        24: [],
    }


def payment():
    return {
        R.SCHEMA_VERSION: 1,
        R.RECORD_TYPE: R.RT_PAYMENT,
        R.ENTITY_UID: ENTITY,
        R.LOGICAL_KEY: "pay:ACME:2026:0001",
        R.CREATED_AT: "2026-05-02T12:00:00.000Z",
        32: "inv:ACME:2026:0001",
        33: 2,
        35: 12100,
        36: "EUR",
        37: 2,
        38: 1,
        39: TX,
        40: 1,
    }


def test_invoice_canonical_round_trips():
    data = R.canonical_bytes(invoice())
    assert decode(data) == invoice()
    assert len(R.canonical_sha256(invoice())) == 32


def test_payment_canonical_round_trips():
    data = R.canonical_bytes(payment())
    assert decode(data) == payment()


def test_canonical_sha256_is_sha256_of_cbor():
    rec = invoice()
    assert R.canonical_sha256(rec) == hashlib.sha256(R.canonical_bytes(rec)).digest()


def test_chain_entry_hash_chains():
    a = R.canonical_sha256(invoice())
    b = R.canonical_sha256(payment())
    e1 = R.entry_hash(R.GENESIS_PREV, a)
    e2 = R.entry_hash(e1, b)
    assert e1 == hashlib.sha256(R.GENESIS_PREV + a).digest()
    assert e2 == hashlib.sha256(e1 + b).digest()
    assert e1 != e2


def test_bignum_amount_supported():
    rec = invoice()
    rec[20] = 18446744073709551616 * 5   # well beyond 64-bit
    data = R.canonical_bytes(rec)
    assert decode(data)[20] == rec[20]


def test_reject_wrong_pubkey_length():
    rec = invoice(); rec[17] = b"\x00" * 32
    with pytest.raises(CanonicalError):
        R.canonical_bytes(rec)


def test_reject_noncanonical_time():
    rec = invoice(); rec[R.CREATED_AT] = "2026-04-01T09:00:00Z"
    with pytest.raises(CanonicalError):
        R.canonical_bytes(rec)


def test_reject_out_of_range_field():
    rec = invoice(); rec[40] = 1   # payment field id on an invoice
    with pytest.raises(CanonicalError):
        R.canonical_bytes(rec)


def test_reject_unknown_record_type():
    rec = invoice(); rec[R.RECORD_TYPE] = 99
    with pytest.raises(CanonicalError):
        R.canonical_bytes(rec)


def test_reject_missing_required_field():
    rec = invoice(); del rec[20]   # gross_amount_minor required
    with pytest.raises(CanonicalError):
        R.canonical_bytes(rec)


def test_reject_bad_money_tuple():
    with pytest.raises(CanonicalError):
        R._money([100, "EUR"])     # 2-tuple, must be 3
    with pytest.raises(CanonicalError):
        R._money([1.0, "EUR", 2])  # float amount
