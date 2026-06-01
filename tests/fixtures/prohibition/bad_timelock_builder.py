# Known-bad fixture (TEST-BUILD-0004): an in-script timelock in a locking-script builder.
def build_locking_script(pubkey_hash, locktime):
    return [locktime, OP_CHECKLOCKTIMEVERIFY, OP_DROP, OP_DUP, pubkey_hash]
