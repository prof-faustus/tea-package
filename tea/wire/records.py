"""Canonical records: the field-id registry, strict validation, and hashing.

Builds on the deterministic-CBOR core (`tea.wire.cbor`). A record is a Python
dict keyed by integer field ids (04 §4.4/§4.12). This module:

  * validates a record against the registry for its `record_type` (closed set,
    partitioned id ranges, REQ-WIRE-0103) — unknown/out-of-range ids rejected;
  * enforces the money 3-tuple, canonical time, and fixed byte-lengths
    (REQ-WIRE-0004/0014/0020/0108);
  * produces `canonical_bytes` and `canonical_sha256` (REQ-WIRE-0040) and the
    audit-chain entry hash (REQ-WIRE-0041/0117h, REQ-DATA-0033).

Hashing choice (documented, pinned by the reproducibility vectors):
  canonical_sha256 = SHA-256(canonical_cbor_bytes)                  -- no domain tag
  entry_hash       = SHA-256(prev_hash ‖ canonical_sha256)         -- no domain tag
  genesis prev_hash = 32 zero bytes (REQ-DATA-0183).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from .cbor import encode, decode, CanonicalError

GENESIS_PREV = b"\x00" * 32
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

# Common envelope (all record types), §4.4.1
SCHEMA_VERSION = 0
RECORD_TYPE = 1
ENTITY_UID = 2
LOGICAL_KEY = 3
CREATED_AT = 4

# record_type enum (§4.4.1 / §4.12), closed set.
RT_INVOICE = 1
RT_PAYMENT = 2
RT_CREDIT_NOTE = 3
RT_ADJUSTMENT = 4
RT_STATEMENT = 5
RT_MESSAGE = 6
RT_WALLET_TRANSFER = 7
RT_KEY_DERIVATION = 8
RT_KEY_CERTIFICATE = 9
RECORD_TYPES = {1, 2, 3, 4, 5, 6, 7, 8, 9}

# field-id range per record type (REQ-WIRE-0103); common envelope is 0..4.
TYPE_RANGES = {
    RT_INVOICE: range(16, 32),
    RT_PAYMENT: range(32, 48),
    RT_MESSAGE: range(48, 56),
    RT_WALLET_TRANSFER: range(56, 64),
    RT_KEY_DERIVATION: range(64, 80),
    RT_KEY_CERTIFICATE: range(80, 96),
    # CREDIT_NOTE/ADJUSTMENT/STATEMENT reuse the invoice/payment shapes and are
    # added with their fields in their stages; their envelope still validates.
    RT_CREDIT_NOTE: range(16, 32),
    RT_ADJUSTMENT: range(16, 48),
    RT_STATEMENT: range(16, 32),
}


# --- field validators ------------------------------------------------------- #

def _uint(v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise CanonicalError("expected unsigned integer")
    return v


def _int(v):
    if isinstance(v, bool) or not isinstance(v, int):
        raise CanonicalError("expected integer")
    return v


def _tstr(v):
    if not isinstance(v, str):
        raise CanonicalError("expected text string")
    if unicodedata.normalize("NFC", v) != v:
        raise CanonicalError("text must be NFC-normalised")
    return v


def _time(v):
    _tstr(v)
    if not _TIME_RE.match(v):
        raise CanonicalError("timestamp must be YYYY-MM-DDTHH:MM:SS.sssZ (REQ-WIRE-0020)")
    return v


def _bstr(n):
    def check(v):
        if not isinstance(v, (bytes, bytearray)):
            raise CanonicalError("expected byte string")
        if len(v) != n:
            raise CanonicalError(f"expected {n}-byte value, got {len(v)}")
        return bytes(v)
    return check


def _pubkey(v):
    return _bstr(33)(v)


def _hash32(v):
    return _bstr(32)(v)


def _money(v):
    """Money 3-tuple [amount_minor int, currency_code tstr, scale uint] (REQ-WIRE-0004)."""
    if not isinstance(v, list) or len(v) != 3:
        raise CanonicalError("money must be a 3-tuple [amount_minor, currency, scale]")
    _int(v[0]); _tstr(v[1]); _uint(v[2])
    return v


def _array(v):
    if not isinstance(v, list):
        raise CanonicalError("expected array")
    return v


# common envelope validators
_ENVELOPE = {
    SCHEMA_VERSION: _uint,
    RECORD_TYPE: _uint,
    ENTITY_UID: _bstr(16),
    LOGICAL_KEY: _tstr,
    CREATED_AT: _time,
}

# per-type field validators (§4.4.2 invoice, §4.4.3 payment, §4.4.4 message,
# §4.4.5 wallet). Additional types' fields are added in their stages.
_FIELDS = {
    RT_INVOICE: {
        16: _tstr,          # invoice_number
        17: _pubkey,        # counterparty_pubkey
        18: _tstr,          # currency_code
        19: _uint,          # currency_scale
        20: _int,           # gross_amount_minor (int/bignum)
        21: _array,         # tax_breakdown
        22: _time,          # due_date
        23: _tstr,          # terms
        24: _array,         # line_items
        25: _tstr,          # receive_address (optional)
    },
    RT_PAYMENT: {
        32: _tstr,          # invoice_logical_key
        33: _uint,          # rail
        34: _tstr,          # protocol_id
        35: _int,           # amount_minor
        36: _tstr,          # currency_code
        37: _uint,          # currency_scale
        38: _uint,          # direction
        39: _hash32,        # txid (LE)
        40: _uint,          # settlement_kind
    },
    RT_MESSAGE: {
        48: _bstr(16),      # thread_uid
        49: _pubkey,        # sender_pubkey
        50: _hash32,        # ciphertext_sha256
    },
    RT_WALLET_TRANSFER: {
        56: _bstr(16),      # wallet_uid
        57: _uint,          # direction
        58: _uint,          # asset_kind
        59: _tstr,          # protocol_id
        60: _int,           # amount_minor
        61: _hash32,        # txid (LE)
    },
    # KEY_DERIVATION (04 §4.18, ids 64-79). The common envelope (0-4) carries
    # scheme_version and entity_uid (the §4.18 ids 64/68 restate those, supplied
    # once via the envelope — DEC-0007); the type-specific fields are 65-74. Carries
    # ONLY public values + the salt commitment; never S/t/salt_det/private scalar
    # (REQ-WIRE-0141; structurally guaranteed because unknown ids are rejected).
    RT_KEY_DERIVATION: {
        65: _uint,          # domain: 0=MASTER_REGISTRATION,1=PAYMENT_ADDRESS,2=INVOICE_NOTE_KEY,3=PAYMENT_NOTE_KEY,4=MESSAGE_KEY
        66: _pubkey,        # master_pub_A (canonical smaller)
        67: _pubkey,        # master_pub_B (canonical larger)
        69: _uint,          # invoice_number
        70: _uint,          # payment_index
        71: _pubkey,        # derived_pubkey (PK_once)
        72: _hash32,        # salt_commitment
        73: _tstr,          # address_text (PAYMENT_ADDRESS; omitted for key-only domains)
        74: _bstr(16),      # counterparty_uid
    },
}

# KEY_DERIVATION domains (field 65)
KD_MASTER_REGISTRATION = 0
KD_PAYMENT_ADDRESS = 1
KD_INVOICE_NOTE_KEY = 2
KD_PAYMENT_NOTE_KEY = 3
KD_MESSAGE_KEY = 4

# required fields per type (envelope always required).
_REQUIRED = {
    RT_INVOICE: {16, 17, 18, 19, 20, 22, 24},
    RT_PAYMENT: {32, 33, 35, 36, 37, 38, 40},
    RT_MESSAGE: {48, 49, 50},
    RT_WALLET_TRANSFER: {56, 57, 58, 60},
    # domain (65), master A/B (66/67), derived_pubkey (71), salt_commitment (72)
    # are always required; invoice_number/payment_index/address_text/counterparty_uid
    # are domain-dependent and enforced by the application.
    RT_KEY_DERIVATION: {65, 66, 67, 71, 72},
}


def validate(record: dict) -> dict:
    """Validate a record against the registry; raise CanonicalError on any violation."""
    if not isinstance(record, dict):
        raise CanonicalError("record must be a map")
    for fid in _ENVELOPE:
        if fid not in record:
            raise CanonicalError(f"missing envelope field {fid}")
    if record[SCHEMA_VERSION] != 1:
        raise CanonicalError("schema_version must be 1")
    rt = record[RECORD_TYPE]
    if rt not in RECORD_TYPES:
        raise CanonicalError(f"unknown record_type {rt}")
    rng = TYPE_RANGES[rt]
    type_fields = _FIELDS.get(rt, {})
    for fid, val in record.items():
        if fid in _ENVELOPE:
            _ENVELOPE[fid](val)
            continue
        if fid not in rng:
            raise CanonicalError(f"field id {fid} out of range for record_type {rt}")
        if type_fields and fid not in type_fields:
            raise CanonicalError(f"unknown field id {fid} for record_type {rt}")
        if type_fields:
            type_fields[fid](val)
    for fid in _REQUIRED.get(rt, set()):
        if fid not in record:
            raise CanonicalError(f"missing required field {fid} for record_type {rt}")
    return record


def canonical_bytes(record: dict) -> bytes:
    """Validate, encode to deterministic CBOR, and assert round-trip identity."""
    validate(record)
    data = encode(record)
    if encode(decode(data)) != data:
        raise CanonicalError("record does not round-trip to identical bytes (REQ-WIRE-0106)")
    return data


def canonical_sha256(record: dict) -> bytes:
    return hashlib.sha256(canonical_bytes(record)).digest()


def entry_hash(prev_hash: bytes, canon_sha256: bytes) -> bytes:
    """Audit-chain entry hash = SHA-256(prev_hash ‖ canonical_sha256) (REQ-DATA-0033)."""
    if len(prev_hash) != 32 or len(canon_sha256) != 32:
        raise CanonicalError("entry_hash inputs must be 32 bytes")
    return hashlib.sha256(prev_hash + canon_sha256).digest()
