"""TEA Package — triple-entry verifiable accounting orchestration over BSV.

The Package owns canonical serialization, the append-only hash-chained audit
log, GL orchestration, the engine bridge, the wallet/matching layer, the API,
and the web UI. It consumes the evidence engine (`tea-bsv`) via the bridge and
never reimplements a cryptographic primitive the engine provides (REQ-EVID-0002).
"""

__version__ = "0.0.0"
