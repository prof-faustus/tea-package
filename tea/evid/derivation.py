"""Persist a shared-address derivation as evidence (REQ-WIRE-0135/0156, REQ-DATA-0163/0165).

The chained KEY_DERIVATION canonical record and the wallet.address row are built
from the SAME engine `derive-shared-address` output, in ONE database transaction —
which is the field-equality guarantee behind the structural DB binding (DEC-0006).
The record carries only public values + the salt commitment (REQ-WIRE-0141).
"""
from __future__ import annotations

from sqlalchemy import text

from tea.wire import records as R
from tea.evid import lineage as LIN


def record_shared_address(conn, *, entity_id: int, wallet_id: int, counterparty_id: int,
                          entity_uid: bytes, counterparty_uid: bytes,
                          master_pub_a: bytes, master_pub_b: bytes,
                          invoice_number: int, payment_index: int,
                          derive_out: dict, created_at: str, logical_key: str) -> dict:
    """Build + chain the KEY_DERIVATION record, then insert the SHARED_ECDH address.

    `derive_out` is the public output of `Bridge.derive_shared_address`
    (derived_pubkey_hex, address_text, salt_commitment_hex). Returns the ids and
    the persisted public values.
    """
    derived_pubkey = bytes.fromhex(derive_out["derived_pubkey_hex"])
    address_text = derive_out["address_text"]
    salt_commitment = bytes.fromhex(derive_out["salt_commitment_hex"])

    record = {
        R.SCHEMA_VERSION: 1,
        R.RECORD_TYPE: R.RT_KEY_DERIVATION,
        R.ENTITY_UID: entity_uid,
        R.LOGICAL_KEY: logical_key,
        R.CREATED_AT: created_at,
        65: R.KD_PAYMENT_ADDRESS,
        66: master_pub_a,
        67: master_pub_b,
        69: invoice_number,
        70: payment_index,
        71: derived_pubkey,
        72: salt_commitment,
        73: address_text,
        74: counterparty_uid,
    }
    canonical_id, audit_seq, entry_hash = LIN.record_canonical_and_chain(
        conn, entity_id=entity_id, logical_key=logical_key, record=record)

    address_id = conn.execute(text(
        "INSERT INTO wallet.address"
        "(wallet_id, entity_id, derivation_path, pubkey, address_text, purpose, "
        " derivation_method, counterparty_id, scheme_version, derivation_domain, "
        " invoice_number, payment_index, key_derivation_canonical_id, salt_commitment) "
        "VALUES (:w,:e,:dp,:pk,:addr,'INVOICE','SHARED_ECDH',:cp,1,1,:inv,:idx,:cid,:sc) "
        "RETURNING id"),
        {"w": wallet_id, "e": entity_id,
         "dp": f"shared/{invoice_number}/{payment_index}",
         "pk": derived_pubkey, "addr": address_text, "cp": counterparty_id,
         "inv": invoice_number, "idx": payment_index,
         "cid": canonical_id, "sc": salt_commitment},
    ).scalar_one()

    return {
        "canonical_id": canonical_id,
        "audit_seq": audit_seq,
        "entry_hash": entry_hash,
        "address_id": address_id,
        "address_text": address_text,
        "derived_pubkey_hex": derived_pubkey.hex(),
    }
