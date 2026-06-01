# Build status — TEA Package

Tracks progress against the build-order exit gates
(`00-overview/04-build-order-for-implementer.md`). A stage is COMPLETE only when
its exit gate is green. No stage proceeds on an unverified lower layer.

| Stage | Scope | Exit gate | Status |
|---|---|---|---|
| 0 | environment, gates, engine | prohibition gate green on the tree; engine selftest/reproduce green; DB reachable | **COMPLETE** |
| 1 | canonical serialization + chain | canonical vectors reproduce byte-for-byte; chain append/verify/immutability green | pending |
| 2 | GL integration | TEST-INT-0001..0014; reports tie out and balance | **in progress** |
| 3 | master keys, derivation, salt | TEST-WIRE/PROP/EVID derivation set; worked vector reproduces | pending |
| 4 | certificate authority | TEST-SEC-0120..0132, TEST-EVID-0013; cert vector reproduces | pending |
| 5 | wallet, node, matching | TEST-WALLET/E2E/REORG | pending |
| 6 | tokens, messaging, disclosure, API, UI | TEST-TOKEN/E2E/API; OpenAPI snapshot | pending |
| 7 | deployment, VM, ops, acceptance | acceptance cold-up green (no network); coverage + requirements-coverage floors met | pending |

## Stage 0 detail

- [x] Repo scaffold + git + CI skeleton (prohibition gate runs first).
- [x] Layer-1 prohibition gate (`tools/prohibition_gate.py`) + known-bad
      self-tests (TEST-BUILD-0001..0006) + clean-tree assertion. **10/10 pass.**
- [x] Toolchains/locks/component versions pinned (`build/manifest.json`).
- [x] Engine integrated: built at pinned ref `52834be`; `selftest` 5/5 +
      `reproduce` 3/3 **green** (executed in WSL); `TEA_BSV_BIN` resolved from
      workspace `[[bin]]`; contract snapshot captured under `contract/`.
- [x] PostgreSQL + pgcrypto reachable: user-owned cluster `127.0.0.1:5455`
      (pg18 dev; deploy/CI pin `postgres:16` — DEC-0003); `pgcrypto` digest
      self-check correct.
- [x] **Stage 0 exit gate verified:** prohibition gate green on the tree;
      engine `selftest` 5/5 + `reproduce` 3/3 green; DB reachable with `pgcrypto`.

## Stage 1 detail (started)

- [x] `tea/wire/cbor.py` — deterministic CBOR core (RFC 8949 §4.2 + Package
      constraints); 69 vector/rule tests green.
- [x] `tea/wire/records.py` — field-id registry, strict validation, canonical
      hashing + audit-chain entry hash; 11 tests green.
- [x] Reproducibility vectors (REQ-WIRE-0100/0101) + `reproduce` test (7 fixtures,
      byte-for-byte).
- [x] Migrations 0001–0007 (`core` schemas, entity/currency/users, gl bootstrap
      hook, `canonical_record` + `audit_chain` + `chain_anchor`) with the
      integrity triggers (`fn_canonical_check`/`_immutable`, `fn_audit_append`/
      `_immutable`, `fn_verify_chain`). Chain tests green: sha-match, append-only
      immutability, gap-free seq, prev/entry linkage, verify-intact
      (TEST-DATA-0001..0006/0050). Applied + tested on the live cluster.
- [ ] Cross-language vectors vs engine (REQ-WIRE-0102) — deferred to the engine
      bridge (Stage 3 / contract stage), since it needs C-EVID.

**Stage 1 exit gate: MET** — canonical vectors reproduce byte-for-byte; chain
append/verify/immutability tests green. (Cross-language-vs-engine vectors land
with the bridge in Stage 3.)

## Stage 2 detail (started)

- [x] `python-accounting` 1.0.1 pinned; installed (Windows Anaconda) reaching the
      WSL DB on 127.0.0.1:5455.
- [x] Migration 0008 (`evid.note` + `evid.lineage` spine).
- [x] GL bootstrap (`tools/gl_bootstrap.py`): `create_all` into the `gl` schema
      via `search_path=gl` (library unmodified, REQ-DATA-0003); 14 GL tables
      created; exact version recorded in `core.component_version` (REQ-DATA-0020/0140).
- [ ] GL posting service (ClientInvoice/SupplierBill/ClientReceipt/JournalEntry
      through the library only, REQ-DATA-0210..0214) + lineage wiring.
- [ ] Integration tests TEST-INT-0001..0014 (reports tie out and balance).
