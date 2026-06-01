"""Stage-3 end-to-end: engine derivation persisted as evidence + a SHARED_ECDH address.

Derive a one-time address via the engine, then in one DB transaction build the
chained KEY_DERIVATION canonical record and the wallet.address row from that same
output (REQ-WIRE-0135/0156, REQ-DATA-0163/0165). Asserts the address is bound to a
chained KEY_DERIVATION record, the stored values equal the engine output, and the
chain verifies. Skips cleanly when the engine/DB is unavailable.
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
from tea.evid import lineage as LIN, derivation as DRV  # noqa: E402
from tea.gl.engine import dsn  # noqa: E402
from tea.wire.cbor import encode  # noqa: E402


def _setup_or_skip():
    b = Bridge()
    try:
        b.version()
    except EngineError as e:
        pytest.skip(f"engine not runnable: {e}")
    try:
        eng = create_engine(dsn())
        with eng.connect() as c:
            c.execute(text("SELECT 1 FROM wallet.address LIMIT 1"))
            c.execute(text("SELECT 1 FROM evid.audit_chain LIMIT 1"))
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"DB/migrations unavailable: {e}")
    return b, eng


def test_derive_then_persist_key_derivation_and_address():
    b, eng = _setup_or_skip()
    we = b.worked_example()
    sk_a, pk_a, pk_b = we["sk_a_1_hex"], we["pk_a_1_hex"], we["pk_b_1_hex"]
    a, bb = sorted([bytes.fromhex(pk_a), bytes.fromhex(pk_b)])
    entity_uid = bytes(16)
    dc = encode({0: 1, 1: 1, 2: a, 3: bb, 4: entity_uid, 5: 1, 6: 0}).hex()

    derive_out = b.derive_shared_address(sk_hex=sk_a, remote_pub_hex=pk_b,
                                         payee_pub_hex=pk_a, dc_hex=dc)
    assert derive_out["address_text"]

    suffix = uuid.uuid4().hex[:8]
    with eng.begin() as c:
        e_id = c.execute(text(
            "INSERT INTO core.entity(name, reporting_currency_id, base_key_ref) "
            "VALUES (:n,0,'custody://e') RETURNING id"), {"n": f"DerivFlow-{suffix}"}).scalar_one()
        w_id = c.execute(text(
            "INSERT INTO wallet.wallet(entity_id,label,hd_root_ref,network) "
            "VALUES (:e,'w','custody://hd','REGTEST') RETURNING id"), {"e": e_id}).scalar_one()
        cp_uid = bytes(range(16))
        cp_id = c.execute(text(
            "INSERT INTO core.counterparty(entity_id,display_name,counterparty_uid,"
            "master_pubkey,master_pubkey_status,master_pubkey_provenance,"
            "master_pubkey_verified_at) VALUES (:e,'CP',:uid,:mp,'VERIFIED','test',now()) "
            "RETURNING id"), {"e": e_id, "uid": cp_uid, "mp": bytes.fromhex(pk_b)}).scalar_one()

        res = DRV.record_shared_address(
            c, entity_id=e_id, wallet_id=w_id, counterparty_id=cp_id,
            entity_uid=entity_uid, counterparty_uid=cp_uid,
            master_pub_a=a, master_pub_b=bb, invoice_number=1, payment_index=0,
            derive_out=derive_out, created_at="2026-04-01T09:00:00.000Z",
            logical_key=f"kd:{suffix}")

    with eng.connect() as c:
        # the address row was accepted by the binding trigger and matches the engine
        row = c.execute(text(
            "SELECT derivation_method, encode(pubkey,'hex') pk, address_text, "
            "key_derivation_canonical_id kd FROM wallet.address WHERE id=:i"),
            {"i": res["address_id"]}).first()
        assert row.derivation_method == "SHARED_ECDH"
        assert row.pk == derive_out["derived_pubkey_hex"]
        assert row.address_text == derive_out["address_text"]
        assert row.kd == res["canonical_id"]
        # the KEY_DERIVATION record is of the right type and is chained
        rt = c.execute(text("SELECT record_type FROM evid.canonical_record WHERE id=:i"),
                       {"i": res["canonical_id"]}).scalar()
        assert rt == "KEY_DERIVATION"
        chained = c.execute(text(
            "SELECT seq FROM evid.audit_chain WHERE canonical_id=:i"),
            {"i": res["canonical_id"]}).scalar()
        assert chained == res["audit_seq"]
        # chain integrity
        assert LIN.verify_chain(c, e_id) is None
