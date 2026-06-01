# Known-good fixture: a clean P2PKH locking-script builder, no prohibited construct.
def build_p2pkh_locking_script(pubkey_hash):
    # OP_DUP OP_HASH160 <20> OP_EQUALVERIFY OP_CHECKSIG — the allowed template.
    return [0x76, 0xa9, push20(pubkey_hash), 0x88, 0xac]


def encode_canonical_record(ctx):
    record = {}
    record["field_id"] = 0x18
    record["commitment"] = ctx.commitment      # public commitment only, no secret
    record["pubkey"] = ctx.counterparty_pubkey
    return to_cbor(record)
