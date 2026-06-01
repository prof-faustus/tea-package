"""The lineage spine: record a canonical record + chain entry and tie it to a GL txn.

REQ-DATA-0023/0072: for every GL transaction the Package triggers there is a
corresponding canonical record and audit-chain entry, joined in `evid.lineage`.
The Package computes canonical bytes (tea.wire) and the chain linkage in Python;
the database triggers independently re-validate both (defence in depth,
REQ-DATA-0030/0033). Tables are addressed by fully-qualified name so the caller's
search_path is irrelevant.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import text

from tea.wire import records as R

ZERO32 = b"\x00" * 32

_RECORD_TYPE_NAME = {
    R.RT_INVOICE: "INVOICE", R.RT_PAYMENT: "PAYMENT", R.RT_CREDIT_NOTE: "CREDIT_NOTE",
    R.RT_ADJUSTMENT: "ADJUSTMENT", R.RT_STATEMENT: "STATEMENT", R.RT_MESSAGE: "MESSAGE",
    R.RT_WALLET_TRANSFER: "WALLET_TRANSFER",
    R.RT_KEY_DERIVATION: "KEY_DERIVATION",
}


def record_canonical_and_chain(conn, *, entity_id: int, logical_key: str, record: dict):
    """Insert the canonical record and append the audit-chain entry. Returns
    (canonical_id, audit_seq, entry_hash). The chain trigger re-validates."""
    data = R.canonical_bytes(record)
    sha = hashlib.sha256(data).digest()
    rt_name = _RECORD_TYPE_NAME[record[R.RECORD_TYPE]]

    canonical_id = conn.execute(text(
        "INSERT INTO evid.canonical_record"
        "(entity_id, record_type, logical_key, canonical_bytes, canonical_sha256, schema_version) "
        "VALUES (:e,:rt,:lk,:cb,:sh,:sv) RETURNING id"),
        {"e": entity_id, "rt": rt_name, "lk": logical_key,
         "cb": data, "sh": sha, "sv": record[R.SCHEMA_VERSION]},
    ).scalar_one()

    last = conn.execute(text(
        "SELECT seq, entry_hash FROM evid.audit_chain "
        "WHERE entity_id=:e ORDER BY seq DESC LIMIT 1"), {"e": entity_id}).first()
    if last is None:
        seq, prev = 1, ZERO32
    else:
        seq, prev = last.seq + 1, bytes(last.entry_hash)
    entry = hashlib.sha256(prev + sha).digest()
    conn.execute(text(
        "INSERT INTO evid.audit_chain(seq, entity_id, canonical_id, prev_hash, entry_hash) "
        "VALUES (:s,:e,:c,:p,:h)"),
        {"s": seq, "e": entity_id, "c": canonical_id, "p": prev, "h": entry})
    return canonical_id, seq, entry


def link_lineage(conn, *, entity_id: int, canonical_id: int, audit_seq: int,
                 gl_txn_id: int | None = None, correlation_id: str | None = None,
                 state: str = "POSTED") -> int:
    """Insert the lineage row joining GL txn <-> canonical record <-> chain entry."""
    corr = correlation_id or str(uuid.uuid4())
    return conn.execute(text(
        "INSERT INTO evid.lineage"
        "(entity_id, correlation_id, gl_txn_id, canonical_id, audit_seq, state) "
        "VALUES (:e,:corr,:g,:c,:s,:st) RETURNING id"),
        {"e": entity_id, "corr": corr, "g": gl_txn_id,
         "c": canonical_id, "s": audit_seq, "st": state},
    ).scalar_one()


def verify_chain(conn, entity_id: int):
    """Return the first broken seq or None (delegates to evid.fn_verify_chain)."""
    return conn.execute(text("SELECT evid.fn_verify_chain(:e)"), {"e": entity_id}).scalar()
