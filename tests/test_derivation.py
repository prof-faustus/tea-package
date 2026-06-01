"""Stage-3 shared-address derivation via the engine (04 §4.20-4.28).

The core stealth-address property: the payee (holding m_payee) and the payer
(holding m_payer) independently derive the SAME one-time public key PK_once and
the SAME salt_commitment, because both arrive at the same ECDH secret S and the
same tweak t. The derivation context DC is built by the Package's deterministic
CBOR (tea.wire.cbor) and consumed by the engine — the cross-language boundary
(REQ-WIRE-0145/0153). The engine returns only public values (REQ-WIRE-0141).

Skips cleanly when the engine is not runnable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.evid.bridge import Bridge, EngineError  # noqa: E402
from tea.wire.cbor import encode  # noqa: E402


def _bridge_or_skip():
    b = Bridge()
    try:
        b.version()
        return b
    except EngineError as e:
        pytest.skip(f"engine not runnable here: {e}")


def _dc_hex(m_a: bytes, m_b: bytes, entity_uid: bytes, invoice_number: int, payment_index: int) -> str:
    # Derivation context DC (§4.23): integer-keyed deterministic CBOR map.
    dc = {0: 1, 1: 1, 2: m_a, 3: m_b, 4: entity_uid, 5: invoice_number, 6: payment_index}
    return encode(dc).hex()


def _keys(b: Bridge):
    we = b.worked_example()
    return we["sk_a_1_hex"], we["pk_a_1_hex"], we["sk_b_1_hex"], we["pk_b_1_hex"]


@pytest.mark.parametrize("salt_rule", ["context", "shared-secret"])
def test_payee_and_payer_derive_same_one_time_address(salt_rule):
    b = _bridge_or_skip()
    sk_a, pk_a, sk_b, pk_b = _keys(b)
    m_payee, m_other = bytes.fromhex(pk_a), bytes.fromhex(pk_b)
    a, bb = sorted([m_payee, m_other])
    dc = _dc_hex(a, bb, bytes(16), invoice_number=1, payment_index=0)

    # payee side: holds sk_a; the other party's key is pk_b; tweak target is M_payee=pk_a
    payee = b.derive_shared_address(sk_hex=sk_a, remote_pub_hex=pk_b,
                                    payee_pub_hex=pk_a, dc_hex=dc, salt_rule=salt_rule)
    # payer side: holds sk_b; the other party's key is pk_a; same tweak target M_payee=pk_a
    payer = b.derive_shared_address(sk_hex=sk_b, remote_pub_hex=pk_a,
                                    payee_pub_hex=pk_a, dc_hex=dc, salt_rule=salt_rule)

    assert payee["derived_pubkey_hex"] == payer["derived_pubkey_hex"]      # same PK_once
    assert payee["address_text"] == payer["address_text"]                  # same P2PKH address
    assert payee["address_text"]                                           # non-empty
    assert payee["salt_commitment_hex"] == payer["salt_commitment_hex"]
    assert len(payee["derived_pubkey_hex"]) == 66                          # 33-byte compressed
    # the engine's A/B ordering matches the Package's CBOR ordering
    assert payee["master_pub_a_hex"] == a.hex()
    assert payee["master_pub_b_hex"] == bb.hex()


def test_derivation_is_deterministic_and_context_bound(salt_rule="context"):
    b = _bridge_or_skip()
    sk_a, pk_a, sk_b, pk_b = _keys(b)
    a, bb = sorted([bytes.fromhex(pk_a), bytes.fromhex(pk_b)])
    dc0 = _dc_hex(a, bb, bytes(16), 1, 0)
    dc1 = _dc_hex(a, bb, bytes(16), 1, 1)   # different payment_index -> different context

    r0 = b.derive_shared_address(sk_hex=sk_a, remote_pub_hex=pk_b, payee_pub_hex=pk_a, dc_hex=dc0)
    r0b = b.derive_shared_address(sk_hex=sk_a, remote_pub_hex=pk_b, payee_pub_hex=pk_a, dc_hex=dc0)
    r1 = b.derive_shared_address(sk_hex=sk_a, remote_pub_hex=pk_b, payee_pub_hex=pk_a, dc_hex=dc1)

    assert r0 == r0b                                          # deterministic (REQ-EVID-0005)
    assert r0["derived_pubkey_hex"] != r1["derived_pubkey_hex"]  # context-bound (different index)
    # no secret material is ever returned
    for v in r0.values():
        assert "sk_once" not in str(v) and "shared_s" not in str(v)
