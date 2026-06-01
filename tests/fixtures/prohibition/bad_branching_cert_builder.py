# Known-bad fixture (TEST-BUILD-0005): a branching certificate locking-script builder.
def build_certificate_locking_script(owner, revoker):
    return [OP_IF, owner, OP_CHECKSIG, OP_ELSE, revoker, OP_CHECKSIG, OP_ENDIF]
