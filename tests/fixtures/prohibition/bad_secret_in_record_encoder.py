# Known-bad fixture (TEST-BUILD-0006): a canonical encoder serializing key material.
def encode_canonical_record(ctx):
    record = {}
    record["field_id"] = 0x18
    record["shared_secret"] = ctx.S            # prohibited: secret scalar into a record
    return to_cbor(record)
