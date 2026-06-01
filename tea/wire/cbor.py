"""Deterministic CBOR (RFC 8949 §4.2) with the Package constraints (04 §4.2/§4.13).

A hand-rolled encoder/decoder so the byte layout is fully under our control and
byte-exact across platforms (REQ-WIRE-0001/0010). The value model is restricted
on purpose:

  int   -> CBOR uint / negint, with bignum (tag 2/3) outside the 64-bit range
  bytes -> CBOR byte string (definite length)
  str   -> CBOR text string (UTF-8, NFC-normalised)
  list  -> CBOR array (definite length)
  dict  -> CBOR map with UNSIGNED-INTEGER keys only (the field-id registry),
           keys emitted sorted by their encoded-key bytes

Floats, NaN, infinity, indefinite-length items, non-shortest encodings,
duplicate keys, and trailing bytes are all rejected (REQ-WIRE-0012/0105/0106).
"""
from __future__ import annotations

import unicodedata

UINT64_MAX = (1 << 64) - 1


class CanonicalError(ValueError):
    """Raised on any violation of the deterministic-canonical rules."""


# --------------------------------------------------------------------------- #
# Encoder
# --------------------------------------------------------------------------- #

def _head(major: int, n: int) -> bytes:
    """Emit a CBOR head for `major` with argument `n` in shortest form."""
    if n < 0:
        raise CanonicalError("internal: negative head argument")
    mt = major << 5
    if n < 24:
        return bytes([mt | n])
    if n < 0x100:
        return bytes([mt | 24, n])
    if n < 0x10000:
        return bytes([mt | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([mt | 26]) + n.to_bytes(4, "big")
    if n <= UINT64_MAX:
        return bytes([mt | 27]) + n.to_bytes(8, "big")
    raise CanonicalError("argument exceeds 64-bit; use bignum")


def _encode_bignum(n: int) -> bytes:
    """CBOR bignum: tag 2 (n>=0) / tag 3 (n<0) over a minimal big-endian magnitude."""
    if n >= 0:
        tag, mag = 2, n
    else:
        tag, mag = 3, -1 - n
    length = (mag.bit_length() + 7) // 8
    content = mag.to_bytes(length, "big") if length else b""
    return _head(6, tag) + _head(2, len(content)) + content


def _encode_int(n: int) -> bytes:
    if 0 <= n <= UINT64_MAX:
        return _head(0, n)
    if -(1 << 64) <= n < 0:
        return _head(1, -1 - n)
    return _encode_bignum(n)


def encode(value) -> bytes:
    """Encode a value in the restricted model to deterministic CBOR bytes."""
    # bool is a subclass of int — reject it explicitly (no major-7 simple values).
    if isinstance(value, bool):
        raise CanonicalError("bool is not a canonical value type")
    if isinstance(value, int):
        return _encode_int(value)
    if isinstance(value, float):
        raise CanonicalError("float is prohibited in canonical records (REQ-WIRE-0012)")
    if isinstance(value, (bytes, bytearray)):
        b = bytes(value)
        return _head(2, len(b)) + b
    if isinstance(value, str):
        nfc = unicodedata.normalize("NFC", value)
        if nfc != value:
            raise CanonicalError("text must be NFC-normalised before encoding (REQ-WIRE-0013)")
        data = nfc.encode("utf-8")
        return _head(3, len(data)) + data
    if isinstance(value, list):
        out = [_head(4, len(value))]
        out.extend(encode(v) for v in value)
        return b"".join(out)
    if isinstance(value, dict):
        return _encode_map(value)
    raise CanonicalError(f"unsupported canonical type: {type(value).__name__}")


def _encode_map(d: dict) -> bytes:
    items = []
    seen = set()
    for k, v in d.items():
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise CanonicalError("map keys must be unsigned-integer field ids")
        if k in seen:
            raise CanonicalError(f"duplicate map key {k}")
        seen.add(k)
        items.append((_head(0, k), encode(v)))
    # RFC 8949 deterministic ordering: sort by the encoded-key bytes.
    items.sort(key=lambda kv: kv[0])
    out = [_head(5, len(items))]
    for ek, ev in items:
        out.append(ek)
        out.append(ev)
    return b"".join(out)


# --------------------------------------------------------------------------- #
# Decoder (strict)
# --------------------------------------------------------------------------- #

def decode(data: bytes):
    """Strictly decode canonical CBOR; reject any non-canonical input and trailing bytes."""
    if not isinstance(data, (bytes, bytearray)):
        raise CanonicalError("decode expects bytes")
    value, off = _decode_at(bytes(data), 0)
    if off != len(data):
        raise CanonicalError("trailing bytes after a complete item (REQ-WIRE-0106)")
    return value


def _read_arg(data: bytes, off: int):
    """Read a CBOR head; return (major, argument, new_offset), enforcing shortest form."""
    if off >= len(data):
        raise CanonicalError("truncated head")
    ib = data[off]
    major = ib >> 5
    ai = ib & 0x1F
    off += 1
    if ai < 24:
        return major, ai, off
    if ai == 24:
        if off >= len(data):
            raise CanonicalError("truncated 1-byte argument")
        n = data[off]
        if n < 24:
            raise CanonicalError("non-shortest integer encoding")
        return major, n, off + 1
    if ai == 25:
        n = int.from_bytes(data[off:off + 2], "big")
        if len(data[off:off + 2]) < 2:
            raise CanonicalError("truncated 2-byte argument")
        if n < 0x100:
            raise CanonicalError("non-shortest integer encoding")
        return major, n, off + 2
    if ai == 26:
        if len(data[off:off + 4]) < 4:
            raise CanonicalError("truncated 4-byte argument")
        n = int.from_bytes(data[off:off + 4], "big")
        if n < 0x10000:
            raise CanonicalError("non-shortest integer encoding")
        return major, n, off + 4
    if ai == 27:
        if len(data[off:off + 8]) < 8:
            raise CanonicalError("truncated 8-byte argument")
        n = int.from_bytes(data[off:off + 8], "big")
        if n < 0x100000000:
            raise CanonicalError("non-shortest integer encoding")
        return major, n, off + 8
    raise CanonicalError("indefinite-length or reserved argument is prohibited")


def _decode_at(data: bytes, off: int):
    major, arg, off = _read_arg(data, off)
    if major == 0:
        return arg, off
    if major == 1:
        return -1 - arg, off
    if major == 2:
        end = off + arg
        if end > len(data):
            raise CanonicalError("truncated byte string")
        return data[off:end], end
    if major == 3:
        end = off + arg
        if end > len(data):
            raise CanonicalError("truncated text string")
        raw = data[off:end]
        try:
            s = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise CanonicalError("invalid UTF-8 in text string") from e
        if unicodedata.normalize("NFC", s) != s:
            raise CanonicalError("text is not NFC-normalised (REQ-WIRE-0013)")
        return s, end
    if major == 4:
        out = []
        for _ in range(arg):
            v, off = _decode_at(data, off)
            out.append(v)
        return out, off
    if major == 5:
        out = {}
        prev_key_bytes = None
        for _ in range(arg):
            kmajor, karg, koff = _read_arg(data, off)
            if kmajor != 0:
                raise CanonicalError("map keys must be unsigned integers")
            key_bytes = data[off:koff]
            if prev_key_bytes is not None and key_bytes <= prev_key_bytes:
                raise CanonicalError("map keys not in canonical ascending order / duplicate")
            prev_key_bytes = key_bytes
            off = koff
            v, off = _decode_at(data, off)
            out[karg] = v
        return out, off
    if major == 6:
        return _decode_bignum(data, arg, off)
    raise CanonicalError("major type 7 (float/simple) is prohibited (REQ-WIRE-0012)")


def _decode_bignum(data: bytes, tag: int, off: int):
    if tag not in (2, 3):
        raise CanonicalError(f"unsupported tag {tag}")
    bmajor, blen, off = _read_arg(data, off)
    if bmajor != 2:
        raise CanonicalError("bignum content must be a byte string")
    end = off + blen
    if end > len(data):
        raise CanonicalError("truncated bignum content")
    content = data[off:end]
    if content and content[0] == 0:
        raise CanonicalError("non-minimal bignum (leading zero byte)")
    mag = int.from_bytes(content, "big") if content else 0
    if tag == 2:
        if mag <= UINT64_MAX:
            raise CanonicalError("bignum used for a value that fits in 64 bits (non-canonical)")
        return mag, end
    n = -1 - mag
    if n >= -(1 << 64):
        raise CanonicalError("negative bignum used for a value that fits in 64 bits")
    return n, end
