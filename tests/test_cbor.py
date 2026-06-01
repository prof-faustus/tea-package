"""Deterministic-CBOR core tests: RFC 8949 Appendix-A vectors + canonical rules.

Pins byte-exactness (REQ-WIRE-0010/0105) and strict rejection (REQ-WIRE-0106).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tea.wire.cbor import encode, decode, CanonicalError  # noqa: E402


def h(s: str) -> bytes:
    return bytes.fromhex(s)


RFC_VECTORS = [
    (0, "00"),
    (1, "01"),
    (10, "0a"),
    (23, "17"),
    (24, "1818"),
    (25, "1819"),
    (100, "1864"),
    (255, "18ff"),
    (256, "190100"),
    (1000, "1903e8"),
    (1000000, "1a000f4240"),
    (1000000000000, "1b000000e8d4a51000"),
    (18446744073709551615, "1bffffffffffffffff"),       # u64 max
    (18446744073709551616, "c249010000000000000000"),   # 2^64 -> bignum tag 2
    (-1, "20"),
    (-10, "29"),
    (-100, "3863"),
    (-1000, "3903e7"),
    (-18446744073709551616, "3bffffffffffffffff"),
    (-18446744073709551617, "c349010000000000000000"),  # negative bignum tag 3
    (b"\x01\x02\x03\x04", "4401020304"),
    (b"", "40"),
    ("", "60"),
    ("a", "6161"),
    ("IETF", "6449455446"),
    ('"\\', "62225c"),
    ([], "80"),
    ([1, 2, 3], "83010203"),
    ([1, [2, 3], [4, 5]], "8301820203820405"),
]


@pytest.mark.parametrize("value,hexbytes", RFC_VECTORS)
def test_encode_matches_rfc(value, hexbytes):
    assert encode(value).hex() == hexbytes


@pytest.mark.parametrize("value,hexbytes", RFC_VECTORS)
def test_decode_round_trip(value, hexbytes):
    assert decode(h(hexbytes)) == value
    assert encode(decode(h(hexbytes))) == h(hexbytes)


def test_map_keys_sorted_by_encoded_bytes():
    # keys provided out of order; canonical output is ascending by encoded key.
    assert encode({3: 4, 1: 2}).hex() == "a201020304"
    # mixed-length keys: 1 (0x01) before 256 (0x190100)
    assert encode({256: 0, 1: 0}).hex() == "a2010019010000"


def test_nested_map():
    assert encode({1: {2: 3}}).hex() == "a101a10203"


def test_reject_float():
    with pytest.raises(CanonicalError):
        encode(1.5)


def test_reject_bool():
    with pytest.raises(CanonicalError):
        encode(True)
    with pytest.raises(CanonicalError):
        encode({1: False})


def test_reject_non_nfc_text():
    # U+00C5 (Å, NFC) vs U+0041 U+030A (A + combining ring, NFD) — reject the NFD form.
    nfd = "Å"
    with pytest.raises(CanonicalError):
        encode(nfd)


def test_decode_rejects_non_shortest_int():
    with pytest.raises(CanonicalError):
        decode(h("1800"))   # 0 encoded in 1 extra byte


def test_decode_rejects_trailing_bytes():
    with pytest.raises(CanonicalError):
        decode(h("0000"))   # two items where one is expected


def test_decode_rejects_indefinite():
    with pytest.raises(CanonicalError):
        decode(h("9fff"))   # indefinite-length array


def test_decode_rejects_unsorted_map_keys():
    with pytest.raises(CanonicalError):
        decode(h("a203040102"))   # keys 3 then 1 — not ascending


def test_decode_rejects_float_major7():
    with pytest.raises(CanonicalError):
        decode(h("f93e00"))   # half-float 1.5


def test_decode_rejects_non_minimal_bignum():
    with pytest.raises(CanonicalError):
        decode(h("c2420001"))   # bignum with leading zero byte
